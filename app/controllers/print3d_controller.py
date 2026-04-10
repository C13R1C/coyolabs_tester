import logging
import os
from datetime import datetime
from decimal import Decimal, InvalidOperation
from uuid import uuid4

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, send_from_directory, url_for
from flask_login import current_user
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.utils import secure_filename

from app.extensions import db
from app.models.notification import Notification
from app.models.print3d_job import Print3DJob
from app.services.audit_service import log_event
from app.services.email_service import send_print3d_ready_email
from app.services.notification_realtime_service import publish_notification_created
from app.services.notification_service import build_3d_message, notify_roles, publish_notifications_safe
from app.utils.authz import min_role_required
from app.utils.roles import is_admin_role
from app.utils.statuses import Print3DJobStatus, PRINT3D_ALLOWED_STATUSES, PRINT3D_ALLOWED_TRANSITIONS


print3d_bp = Blueprint("print3d", __name__, url_prefix="/prints3d")
logger = logging.getLogger(__name__)

ALLOWED_PRINT3D_EXTENSIONS = {"stl", "obj", "3mf", "gcode"}
MAX_PRINT3D_FILE_SIZE_BYTES = 25 * 1024 * 1024
STATUS_REQUESTED = Print3DJobStatus.REQUESTED
MAX_PRINT3D_FILES_PER_SUBMISSION = 15
MAX_ACTIVE_PRINT3D_JOBS_PER_USER = 2
ACTIVE_PRINT3D_STATUSES = {
    Print3DJobStatus.REQUESTED,
    Print3DJobStatus.QUOTED,
    Print3DJobStatus.IN_PROGRESS,
    Print3DJobStatus.READY,
    Print3DJobStatus.READY_FOR_PICKUP,
}
PRINT3D_PRICE_PER_GRAM = Decimal("3.00")


def _normalize_print3d_status(raw_status: str | None) -> str:
    return (raw_status or "").strip().upper()


def _can_transition_status(current_status: str, next_status: str) -> bool:
    allowed = PRINT3D_ALLOWED_TRANSITIONS.get(current_status, set())
    return next_status in allowed


def _status_badge_class(status: str | None) -> str:
    normalized = _normalize_print3d_status(status)
    if normalized in {Print3DJobStatus.READY, Print3DJobStatus.READY_FOR_PICKUP, Print3DJobStatus.DELIVERED}:
        return "status-ok"
    if normalized == Print3DJobStatus.CANCELED:
        return "status-bad"
    if normalized == Print3DJobStatus.IN_PROGRESS:
        return "status-neutral"
    return "status-warn"


def _save_print3d_file(file_storage):
    if not file_storage or not file_storage.filename:
        return None, None, None, "Debes adjuntar un archivo para la impresión 3D."

    raw_name = secure_filename(file_storage.filename or "")
    if "." not in raw_name:
        return None, None, None, "El archivo debe incluir una extensión válida (.stl, .obj, .3mf, .gcode)."

    ext = raw_name.rsplit(".", 1)[1].lower()
    if ext not in ALLOWED_PRINT3D_EXTENSIONS:
        return None, None, None, "Tipo de archivo no permitido. Usa STL, OBJ, 3MF o GCODE."

    file_storage.stream.seek(0, os.SEEK_END)
    size_bytes = file_storage.stream.tell()
    file_storage.stream.seek(0)
    if size_bytes <= 0:
        return None, None, None, "El archivo adjunto está vacío."
    if size_bytes > MAX_PRINT3D_FILE_SIZE_BYTES:
        return None, None, None, "El archivo supera el tamaño máximo permitido (25 MB)."

    uploads_rel_dir = os.path.join("uploads", "prints3d")
    uploads_abs_dir = os.path.join(current_app.root_path, "static", uploads_rel_dir)
    os.makedirs(uploads_abs_dir, exist_ok=True)

    unique_name = f"{uuid4().hex}.{ext}"
    abs_path = os.path.join(uploads_abs_dir, unique_name)
    file_storage.save(abs_path)

    return f"{uploads_rel_dir}/{unique_name}", raw_name, abs_path, None


def _active_print3d_jobs_count(user_id: int) -> int:
    return (
        Print3DJob.query
        .filter(Print3DJob.requester_user_id == user_id)
        .filter(Print3DJob.status.in_(list(ACTIVE_PRINT3D_STATUSES)))
        .count()
    )


def _build_ready_notification(job: Print3DJob) -> Notification | None:
    """Build requester notification for READY_FOR_PICKUP once."""
    if job.ready_notified_at is not None:
        return None

    requester = job.requester_user
    if not requester or not requester.email:
        return None

    return Notification(
        user_id=job.requester_user_id,
        title="Tu impresión 3D está lista",
        message=f"Tu solicitud #{job.id} ({job.title}) está lista para recoger.",
        link=url_for("print3d.my_jobs"),
    )


def _build_canceled_notification(job: Print3DJob) -> Notification | None:
    if not job.requester_user_id:
        return None
    reason = (job.admin_note or "").strip()
    reason_text = f" Motivo: {reason}." if reason else ""
    return Notification(
        user_id=job.requester_user_id,
        title="Tu solicitud 3D fue cancelada",
        message=f"La solicitud #{job.id} ({job.title}) fue cancelada.{reason_text}",
        link=url_for("print3d.my_jobs"),
    )


def _notify_admins_for_new_job(job: Print3DJob) -> list[Notification]:
    requester_name = getattr(current_user, "full_name", None) or getattr(current_user, "email", "Usuario")
    return notify_roles(
        roles=["ADMIN", "SUPERADMIN", "STAFF"],
        title="Nueva solicitud de impresión 3D",
        message=build_3d_message("created", actor_name=requester_name, job_id=job.id, title=job.title),
        link=url_for("print3d.admin_detail", job_id=job.id),
        priority="low",
    )


@print3d_bp.route("/", methods=["GET"])
@min_role_required("STUDENT")
def print3d_home():
    if is_admin_role(current_user.role):
        return redirect(url_for("print3d.admin_list"))
    return redirect(url_for("print3d.my_jobs"))


@print3d_bp.route("/my", methods=["GET"])
@min_role_required("STUDENT")
def my_jobs():
    if is_admin_role(current_user.role):
        return redirect(url_for("print3d.admin_list"))

    jobs = (
        Print3DJob.query
        .filter(Print3DJob.requester_user_id == current_user.id)
        .order_by(Print3DJob.created_at.desc())
        .all()
    )
    return render_template(
        "prints3d/my_list.html",
        jobs=jobs,
        active_page="prints3d",
        status_badge_class=_status_badge_class,
    )


@print3d_bp.route("/new", methods=["GET", "POST"])
@min_role_required("STUDENT")
def new_job():
    if is_admin_role(current_user.role):
        return redirect(url_for("print3d.admin_list"))

    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        description = (request.form.get("description") or "").strip()
        files = [f for f in request.files.getlist("model_file") if f and f.filename]

        if not title:
            flash("El título de la solicitud es obligatorio.", "error")
            return redirect(url_for("print3d.new_job"))

        if not files:
            flash("Debes seleccionar al menos un archivo 3D.", "error")
            return redirect(url_for("print3d.new_job"))

        if len(files) > MAX_PRINT3D_FILES_PER_SUBMISSION:
            flash(f"Máximo {MAX_PRINT3D_FILES_PER_SUBMISSION} archivos por solicitud.", "error")
            return redirect(url_for("print3d.new_job"))

        active_jobs = _active_print3d_jobs_count(current_user.id)
        if active_jobs >= MAX_ACTIVE_PRINT3D_JOBS_PER_USER:
            flash(
                f"Ya tienes {active_jobs} solicitudes activas. Espera a que avance alguna antes de enviar más.",
                "warning",
            )
            return redirect(url_for("print3d.new_job"))

        if active_jobs + len(files) > MAX_ACTIVE_PRINT3D_JOBS_PER_USER:
            available = MAX_ACTIVE_PRINT3D_JOBS_PER_USER - active_jobs
            flash(
                f"Solo puedes enviar {available} archivo(s) más por ahora. Límite activo: {MAX_ACTIVE_PRINT3D_JOBS_PER_USER}.",
                "warning",
            )
            return redirect(url_for("print3d.new_job"))

        created_job_ids: list[int] = []
        saved_paths: list[str] = []
        admin_notifications: list[Notification] = []
        try:
            for file_storage in files:
                file_ref, original_filename, abs_path, file_error = _save_print3d_file(file_storage)
                if file_error:
                    flash(file_error, "error")
                    raise ValueError("print3d_file_validation_error")

                file_size_bytes = int(file_storage.content_length or 0)
                if file_size_bytes <= 0:
                    file_storage.stream.seek(0, os.SEEK_END)
                    file_size_bytes = int(file_storage.stream.tell())
                    file_storage.stream.seek(0)

                job = Print3DJob(
                    requester_user_id=current_user.id,
                    title=title if len(files) == 1 else f"{title} ({original_filename})",
                    description=description or None,
                    file_ref=file_ref,
                    original_filename=original_filename,
                    file_size_bytes=file_size_bytes,
                    status=STATUS_REQUESTED,
                    updated_at=datetime.utcnow(),
                )
                db.session.add(job)
                db.session.flush()
                created_job_ids.append(job.id)
                saved_paths.append(abs_path)
                admin_notifications.extend(_notify_admins_for_new_job(job))

                log_event(
                    module="PRINT3D",
                    action="PRINT3D_REQUEST_CREATED",
                    user_id=current_user.id,
                    entity_label=f"Print3DJob #{job.id}",
                    description=f"Solicitud 3D creada: {job.title}",
                    metadata={"job_id": job.id, "status": job.status},
                )

            db.session.commit()
        except (ValueError, SQLAlchemyError) as err:
            db.session.rollback()
            had_validation_flash = False
            for path in saved_paths:
                try:
                    if path and os.path.exists(path):
                        os.remove(path)
                except OSError:
                    logger.warning("No se pudo limpiar archivo 3D tras error de validación", exc_info=True)
            if isinstance(err, ValueError):
                had_validation_flash = True
            if not had_validation_flash:
                flash("No se pudo crear la solicitud de impresión 3D. Intenta nuevamente.", "error")
            return redirect(url_for("print3d.new_job"))

        for notif in admin_notifications:
            try:
                publish_notification_created(notif)
            except Exception:
                logger.warning(
                    "SSE publish failed after print3d request creation",
                    exc_info=True,
                    extra={"notification_id": notif.id, "target_user_id": notif.user_id},
                )

        flash(f"Solicitud enviada correctamente. Archivos registrados: {len(created_job_ids)}.", "success")
        return redirect(url_for("print3d.my_jobs"))

    return render_template("prints3d/new.html", active_page="prints3d")


@print3d_bp.route("/<int:job_id>/download", methods=["GET"])
@min_role_required("STUDENT")
def download_file(job_id: int):
    job = Print3DJob.query.get_or_404(job_id)
    if job.requester_user_id != current_user.id and not is_admin_role(current_user.role):
        abort(403)

    if not job.file_ref:
        abort(404)

    ref_norm = os.path.normpath(job.file_ref)
    expected_prefix = os.path.join("uploads", "prints3d")
    if not ref_norm.startswith(expected_prefix):
        abort(404)

    rel_dir, filename = os.path.split(ref_norm)
    abs_dir = os.path.join(current_app.root_path, "static", rel_dir)
    abs_path = os.path.join(abs_dir, filename)

    if not os.path.isfile(abs_path):
        abort(404)

    log_event(
        module="PRINT3D",
        action="PRINT3D_FILE_DOWNLOADED",
        user_id=current_user.id,
        entity_label=f"Print3DJob #{job.id}",
        description="Descarga de archivo 3D",
        metadata={"job_id": job.id},
    )
    db.session.commit()

    return send_from_directory(abs_dir, filename, as_attachment=True, download_name=job.original_filename)


@print3d_bp.route("/admin", methods=["GET"])
@min_role_required("ADMIN")
def admin_list():
    jobs = (
        Print3DJob.query
        .order_by(Print3DJob.created_at.desc())
        .all()
    )
    return render_template(
        "prints3d/admin_list.html",
        jobs=jobs,
        active_page="prints3d",
        status_badge_class=_status_badge_class,
    )


@print3d_bp.route("/admin/<int:job_id>", methods=["GET"])
@min_role_required("ADMIN")
def admin_detail(job_id: int):
    job = Print3DJob.query.get_or_404(job_id)
    allowed_next = PRINT3D_ALLOWED_TRANSITIONS.get(_normalize_print3d_status(job.status), set())
    return render_template(
        "prints3d/admin_detail.html",
        job=job,
        active_page="prints3d",
        status_badge_class=_status_badge_class,
        allowed_next=allowed_next,
        price_per_gram=PRINT3D_PRICE_PER_GRAM,
    )


@print3d_bp.route("/admin/<int:job_id>/status", methods=["POST"])
@min_role_required("ADMIN")
def admin_set_status(job_id: int):
    job = Print3DJob.query.get_or_404(job_id)

    target_status = _normalize_print3d_status(request.form.get("status"))
    current_status = _normalize_print3d_status(job.status)
    admin_note = (request.form.get("admin_note") or "").strip()
    estimated_grams_raw = (request.form.get("estimated_grams") or "").strip()
    if estimated_grams_raw:
        try:
            grams_estimated_value = Decimal(estimated_grams_raw)
        except InvalidOperation:
            flash("Los gramos estimados deben ser un número válido.", "error")
            return redirect(url_for("print3d.admin_detail", job_id=job.id))
        if grams_estimated_value < 0:
            flash("Los gramos estimados no pueden ser negativos.", "error")
            return redirect(url_for("print3d.admin_detail", job_id=job.id))
        job.grams_estimated = grams_estimated_value
        job.price_per_gram = PRINT3D_PRICE_PER_GRAM
        job.total_estimated = (grams_estimated_value * PRINT3D_PRICE_PER_GRAM).quantize(Decimal("0.01"))

    if target_status not in PRINT3D_ALLOWED_STATUSES:
        flash("Estado de impresión 3D no válido.", "error")
        return redirect(url_for("print3d.admin_detail", job_id=job.id))

    if target_status == Print3DJobStatus.CANCELED and not admin_note:
        flash("Debes capturar el motivo para rechazar/cancelar la solicitud.", "error")
        return redirect(url_for("print3d.admin_detail", job_id=job.id))

    statuses_requiring_estimate = {
        Print3DJobStatus.QUOTED,
        Print3DJobStatus.IN_PROGRESS,
        Print3DJobStatus.READY,
        Print3DJobStatus.READY_FOR_PICKUP,
        Print3DJobStatus.DELIVERED,
    }
    if target_status in statuses_requiring_estimate and job.grams_estimated is None:
        flash("Debes capturar primero los gramos estimados para calcular el total estimado.", "error")
        return redirect(url_for("print3d.admin_detail", job_id=job.id))

    if target_status == Print3DJobStatus.CANCELED:
        job.admin_note = admin_note

    if current_status == target_status:
        db.session.commit()
        flash("El trabajo ya se encuentra en ese estado.", "info")
        return redirect(url_for("print3d.admin_detail", job_id=job.id))

    if not _can_transition_status(current_status, target_status):
        flash("Transición de estado no permitida para este trabajo.", "error")
        return redirect(url_for("print3d.admin_detail", job_id=job.id))

    job.status = target_status
    should_notify_ready = False
    should_notify_canceled = False

    log_event(
        module="PRINT3D",
        action="PRINT3D_STATUS_CHANGED",
        user_id=current_user.id,
        entity_label=f"Print3DJob #{job.id}",
        description=f"Estado de impresión 3D cambiado de {current_status} a {target_status}",
        metadata={"job_id": job.id, "from": current_status, "to": target_status},
    )

    if target_status == Print3DJobStatus.READY_FOR_PICKUP:
        ready_candidate = _build_ready_notification(job)
        if ready_candidate is None:
            log_event(
                module="PRINT3D",
                action="PRINT3D_READY_NOTIFY_SKIPPED",
                user_id=current_user.id,
                entity_label=f"Print3DJob #{job.id}",
                description="Notificación de trabajo listo omitida por idempotencia",
                metadata={
                    "job_id": job.id,
                    "target_user_id": job.requester_user_id,
                    "reason": "already_notified_or_missing_user",
                },
            )
        else:
            should_notify_ready = True
    elif target_status == Print3DJobStatus.CANCELED:
        should_notify_canceled = True

    db.session.commit()
    created_user_notification: Notification | None = None
    additional_status_notification: Notification | None = None
    if should_notify_ready:
        created_user_notification = _build_ready_notification(job)
        if created_user_notification is not None:
            db.session.add(created_user_notification)
            job.ready_notified_at = datetime.utcnow()
            db.session.commit()
    elif should_notify_canceled:
        created_user_notification = _build_canceled_notification(job)
        if created_user_notification is not None:
            db.session.add(created_user_notification)
            db.session.commit()
    elif target_status in {Print3DJobStatus.QUOTED, Print3DJobStatus.IN_PROGRESS, Print3DJobStatus.DELIVERED}:
        additional_status_notification = Notification(
            user_id=job.requester_user_id,
            title="Tu solicitud 3D fue actualizada",
            message=build_3d_message(
                "status",
                actor_name=(current_user.full_name or current_user.email),
                job_id=job.id,
                title=job.title,
            ),
            link=url_for("print3d.my_jobs"),
        )
        setattr(additional_status_notification, "_priority", "medium")
        db.session.add(additional_status_notification)
        db.session.commit()

    notifications_to_publish = []
    if created_user_notification is not None:
        notifications_to_publish.append(created_user_notification)
    if additional_status_notification is not None:
        notifications_to_publish.append(additional_status_notification)
    publish_notifications_safe(
        notifications_to_publish,
        logger=logger,
        event_label="print3d status update",
        extra={"job_id": job.id, "target_status": target_status},
    )

    if created_user_notification is not None:
        if target_status == Print3DJobStatus.READY_FOR_PICKUP and job.requester_user and job.requester_user.email:
            jobs_url = url_for("print3d.my_jobs", _external=True)
            email_sent = False
            try:
                send_print3d_ready_email(
                    job.requester_user.email,
                    job_id=job.id,
                    job_title=job.title,
                    jobs_url=jobs_url,
                )
                email_sent = True
            except Exception:
                logger.warning(
                    "Failed to send print3d READY email",
                    exc_info=True,
                    extra={"job_id": job.id, "target_user_id": job.requester_user_id},
                )
            log_event(
                module="PRINT3D",
                action="PRINT3D_READY_NOTIFIED",
                user_id=current_user.id,
                entity_label=f"Print3DJob #{job.id}",
                description="Notificación de trabajo listo enviada al solicitante",
                metadata={
                    "job_id": job.id,
                    "target_user_id": job.requester_user_id,
                    "email_sent": email_sent,
                    "notification_channel": ["in_app", "email"],
                },
            )
            db.session.commit()

    flash("Estado actualizado correctamente.", "success")
    return redirect(url_for("print3d.admin_detail", job_id=job.id))
