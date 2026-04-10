import os
from uuid import uuid4
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, current_app
from flask_login import current_user
from werkzeug.utils import secure_filename

from app.extensions import db
from app.models.lost_found import LostFound
from app.models.material import Material
from app.models.notification import Notification
from app.services.notification_service import build_notification, notify_roles, publish_notifications_safe
from app.utils.authz import min_role_required
from app.utils.roles import is_admin_role


lostfound_bp = Blueprint("lostfound", __name__, url_prefix="/lostfound")
ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
MAX_IMAGE_SIZE_BYTES = 5 * 1024 * 1024
LOSTFOUND_STATUS_UI_LABELS = {
    "REPORTED": "Pérdida reportada",
    "IN_STORAGE": "Hallazgo en resguardo",
    "RETURNED": "Entregado a propietario",
}


def _save_evidence_image(file_storage):
    if not file_storage or not file_storage.filename:
        return None, None

    raw_name = secure_filename(file_storage.filename or "")
    if "." not in raw_name:
        return None, "La imagen debe tener extensión válida (.jpg, .jpeg, .png, .webp)."

    ext = raw_name.rsplit(".", 1)[1].lower()
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        return None, "Tipo de archivo no permitido. Usa JPG, JPEG, PNG o WEBP."

    mime = (file_storage.mimetype or "").lower()
    if not mime.startswith("image/"):
        return None, "El archivo seleccionado no es una imagen válida."

    file_storage.stream.seek(0, os.SEEK_END)
    size_bytes = file_storage.stream.tell()
    file_storage.stream.seek(0)
    if size_bytes > MAX_IMAGE_SIZE_BYTES:
        return None, "La imagen supera el tamaño máximo permitido (5 MB)."

    uploads_rel_dir = os.path.join("uploads", "lostfound")
    uploads_abs_dir = os.path.join(current_app.root_path, "static", uploads_rel_dir)
    os.makedirs(uploads_abs_dir, exist_ok=True)

    unique_name = f"{uuid4().hex}.{ext}"
    abs_path = os.path.join(uploads_abs_dir, unique_name)
    file_storage.save(abs_path)

    return f"{uploads_rel_dir}/{unique_name}", None


def _lostfound_status_label(status: str | None) -> str:
    normalized = (status or "").strip().upper()
    return LOSTFOUND_STATUS_UI_LABELS.get(normalized, normalized or "-")


@lostfound_bp.route("/", methods=["GET"])
@min_role_required("STUDENT")
def lostfound_home():
    if is_admin_role(current_user.role):
        return redirect(url_for("lostfound.list_items"))

    return redirect(url_for("lostfound.list_items"))


@lostfound_bp.route("/list", methods=["GET"])
@min_role_required("STUDENT")
def list_items():
    status = (request.args.get("status") or "").strip().upper()

    q = LostFound.query
    if not is_admin_role(current_user.role):
        q = q.filter(LostFound.status.in_(["REPORTED", "IN_STORAGE"]))
    elif status in {"REPORTED", "IN_STORAGE", "RETURNED"}:
        q = q.filter(LostFound.status == status)

    items = q.order_by(LostFound.created_at.desc()).all()
    return render_template(
        "lostfound/list.html",
        items=items,
        status=status,
        status_label_fn=_lostfound_status_label,
        active_page="lostfound"
    )


@lostfound_bp.route("/<int:item_id>", methods=["GET"])
@min_role_required("STUDENT")
def detail(item_id: int):
    item = LostFound.query.get(item_id)
    if not item:
        abort(404)

    return render_template(
        "lostfound/detail.html",
        item=item,
        status_label_fn=_lostfound_status_label,
        active_page="lostfound",
    )


@lostfound_bp.route("/admin/new", methods=["GET", "POST"])
@min_role_required("ADMIN")
def admin_new():
    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        description = (request.form.get("description") or "").strip()
        location = (request.form.get("location") or "").strip()
        report_kind = (request.form.get("report_kind") or "").strip().lower()
        evidence_file = request.files.get("evidence_file")
        material_id = request.form.get("material_id")

        if not title:
            flash("El título es obligatorio.", "error")
            return redirect(url_for("lostfound.admin_new"))

        if report_kind not in {"lost", "found"}:
            flash("Debes seleccionar la categoría del registro.", "error")
            return redirect(url_for("lostfound.admin_new"))

        mat = None
        if material_id:
            try:
                material_id_int = int(material_id)
                mat = Material.query.get(material_id_int)
                if not mat:
                    flash("material_id no existe.", "error")
                    return redirect(url_for("lostfound.admin_new"))
            except ValueError:
                flash("material_id inválido.", "error")
                return redirect(url_for("lostfound.admin_new"))

        saved_image_ref, image_error = _save_evidence_image(evidence_file)
        if image_error:
            flash(image_error, "error")
            return redirect(url_for("lostfound.admin_new"))

        item = LostFound(
            reported_by_user_id=getattr(current_user, "id", None),
            material_id=mat.id if mat else None,
            title=title,
            description=description or None,
            location=location or None,
            evidence_ref=saved_image_ref,
            status="REPORTED" if report_kind == "lost" else "IN_STORAGE",
        )

        db.session.add(item)
        db.session.commit()

        if report_kind == "lost":
            notif_title = "Nueva pérdida reportada"
            notif_message = f"Se registró un caso de objeto perdido: {item.title}."
        else:
            notif_title = "Nuevo hallazgo registrado"
            notif_message = f"Se registró un hallazgo en resguardo: {item.title}."

        notifications_created = notify_roles(
            roles=["ADMIN", "SUPERADMIN", "STAFF"],
            title=notif_title,
            message=notif_message,
            link=url_for("lostfound.detail", item_id=item.id),
            actor_name=(current_user.full_name or current_user.email),
            entity_name=f"Caso #{item.id}",
            priority="low",
        )

        db.session.commit()
        publish_notifications_safe(
            notifications_created,
            logger=current_app.logger,
            event_label="lostfound creation",
            extra={"lostfound_id": item.id},
        )

        flash("Registro creado.", "success")
        return redirect(url_for("lostfound.detail", item_id=item.id))

    return render_template("lostfound/admin_new.html", active_page="lostfound")


@lostfound_bp.route("/admin/<int:item_id>/status", methods=["POST"])
@min_role_required("ADMIN")
def admin_set_status(item_id: int):
    item = LostFound.query.get(item_id)
    if not item:
        abort(404)

    new_status = (request.form.get("status") or "").strip().upper()
    admin_note = (request.form.get("admin_note") or "").strip()

    if new_status not in {"REPORTED", "IN_STORAGE", "RETURNED"}:
        flash("Status inválido.", "error")
        return redirect(url_for("lostfound.detail", item_id=item.id))

    item.status = new_status
    item.admin_note = admin_note or None

    status_labels = {
        "REPORTED": "pérdida reportada",
        "IN_STORAGE": "resguardo administrativo",
        "RETURNED": "entregado a propietario",
    }
    notifications_created: list[Notification] = notify_roles(
        roles=["ADMIN", "SUPERADMIN", "STAFF"],
        title="Caso de objeto perdido actualizado",
        message=f"El caso cambió a {status_labels.get(new_status, new_status)}.",
        link=url_for("lostfound.detail", item_id=item.id),
        actor_name=(current_user.full_name or current_user.email),
        entity_name=f"Caso #{item.id}",
        priority="medium",
    )
    if item.reported_by_user_id:
        notifications_created.append(
            build_notification(
                user_id=item.reported_by_user_id,
                title="Tu reporte de objeto perdido fue actualizado",
                message=f"Tu reporte ahora está en estado: {status_labels.get(new_status, new_status)}.",
                link=url_for("lostfound.detail", item_id=item.id),
                actor_name=(current_user.full_name or current_user.email),
                entity_name=f"Caso #{item.id}",
                priority="medium",
            )
        )
    db.session.commit()
    publish_notifications_safe(
        notifications_created,
        logger=current_app.logger,
        event_label="lostfound status update",
        extra={"lostfound_id": item.id, "status": new_status},
    )

    flash("Estado actualizado.", "success")
    return redirect(url_for("lostfound.detail", item_id=item.id))
