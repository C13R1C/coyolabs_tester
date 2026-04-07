import logging
import os
import base64
import binascii
from datetime import datetime, timedelta
import json
from uuid import uuid4

from flask import Blueprint, current_app, render_template, request, redirect, url_for, flash
from flask_login import current_user
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func
from sqlalchemy.orm import joinedload

from app.utils.roles import ROLE_STUDENT, ROLE_TEACHER, is_admin_role, normalize_role
from app.models.reservation_item import ReservationItem
from app.models.material import Material
from app.models.lab_ticket import LabTicket
from app.models.ticket_item import TicketItem
from app.models.notification import Notification
from app.models.subject import Subject
from app.models.teacher_academic_load import TeacherAcademicLoad
from app.models.user import User

from app.extensions import db
from app.models.reservation import Reservation
from app.services.audit_service import log_event
from app.services.debt_service import user_has_open_debts
from app.services.notification_realtime_service import publish_notification_created
from app.services.reservation_service import approve_reservation, reject_reservation
from app.services.ticket_service import (
    add_material_to_ticket,
    apply_ticket_item_status,
    close_ticket,
    request_ticket_closure,
    sync_ticket_ready_status,
    validate_ticket_active,
)
from app.controllers.inventory_controller import _is_inactive_status
from app.utils.authz import min_role_required
from app.utils.statuses import (
    BLOCKING_LAB_TICKET_STATUSES,
    LabTicketStatus,
    ReservationStatus,
    TicketItemStatus,
    is_active_lab_ticket_status,
    is_lab_ticket_closure_requested,
)
from app.utils.validators import normalize_and_validate_group_code
from app.constants import ROOMS

reservations_bp = Blueprint("reservations", __name__, url_prefix="/reservations")
logger = logging.getLogger(__name__)
INACTIVE_MATERIAL_STATUSES = ("baja", "de baja", "inactivo")


def _is_professor_role(role: str | None) -> bool:
    normalized = normalize_role(role)
    return normalized == ROLE_TEACHER


def _is_student_role(role: str | None) -> bool:
    return normalize_role(role) == ROLE_STUDENT


def _is_active_ticket_status(status: str | None) -> bool:
    return is_active_lab_ticket_status(status)


def _is_ticket_closure_requested(status: str | None) -> bool:
    return is_lab_ticket_closure_requested(status)


def _is_ticket_operable_for_item_updates(status: str | None) -> bool:
    normalized = (status or "").strip().upper()
    return normalized in {
        LabTicketStatus.OPEN,
        LabTicketStatus.READY_FOR_PICKUP,
        LabTicketStatus.CLOSURE_REQUESTED,
    }


def _exclude_inactive_materials(query):
    normalized_status = func.trim(func.lower(func.coalesce(Material.status, "")))
    return query.filter(~normalized_status.in_(INACTIVE_MATERIAL_STATUSES))


def _sync_ticket_ready_status(ticket: LabTicket) -> None:
    sync_ticket_ready_status(ticket)


def _professor_assignments(teacher_id: int) -> list[TeacherAcademicLoad]:
    return (
        TeacherAcademicLoad.query
        .options(joinedload(TeacherAcademicLoad.subject))
        .filter(TeacherAcademicLoad.teacher_id == teacher_id)
        .all()
    )


def _build_requester_name() -> str:
    full_name = (getattr(current_user, "full_name", "") or "").strip()
    if full_name:
        return full_name

    email = (getattr(current_user, "email", "") or "").strip()
    if email:
        return email

    user_id = getattr(current_user, "id", None)
    return f"Usuario #{user_id}" if user_id is not None else "Usuario"


def _save_signature_image(signature_data_url: str) -> tuple[str | None, str | None]:
    prefix = "data:image/png;base64,"
    raw = (signature_data_url or "").strip()
    if not raw.startswith(prefix):
        return None, "Firma inválida. Vuelve a firmar en el recuadro."

    encoded = raw[len(prefix):]
    try:
        payload = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError):
        return None, "No se pudo procesar la firma digital."

    if len(payload) < 200:
        return None, "La firma está vacía o incompleta."
    if len(payload) > 1024 * 1024:
        return None, "La firma excede el tamaño máximo permitido."

    uploads_rel_dir = os.path.join("uploads", "signatures")
    uploads_abs_dir = os.path.join(current_app.root_path, "static", uploads_rel_dir)
    os.makedirs(uploads_abs_dir, exist_ok=True)

    filename = f"{uuid4().hex}.png"
    abs_path = os.path.join(uploads_abs_dir, filename)
    with open(abs_path, "wb") as fp:
        fp.write(payload)

    return f"{uploads_rel_dir}/{filename}", None


def parse_date(value: str):
    return datetime.strptime(value, "%Y-%m-%d").date()


def parse_time(value: str):
    return datetime.strptime(value, "%H:%M").time()


def duration_minutes(start_t, end_t) -> int:
    dt1 = datetime.combine(datetime.today(), start_t)
    dt2 = datetime.combine(datetime.today(), end_t)
    return int((dt2 - dt1).total_seconds() / 60)


def overlaps(room: str, date_, start_t, end_t) -> bool:
    """
    True si hay solapamiento con una reserva aprobada en el mismo salón/fecha.
    Condición de solapamiento: start < existing_end AND end > existing_start
    """
    q = (
        Reservation.query
        .filter(Reservation.room == room)
        .filter(Reservation.date == date_)
        .filter(Reservation.status == ReservationStatus.APPROVED)
        .filter(Reservation.start_time < end_t)
        .filter(Reservation.end_time > start_t)
    )
    return q.first() is not None


def get_week_start(date_value):
    return date_value - timedelta(days=date_value.weekday())


def build_week_days(week_start):
    return [week_start + timedelta(days=i) for i in range(7)]



TIME_SLOT_RANGES = [
    ("08:00", "10:00"),
    ("10:00", "12:00"),
    ("12:00", "14:00"),
    ("14:00", "16:00"),
    ("16:00", "18:00"),
]


def _build_time_slots() -> list[tuple[str, str, object, object]]:
    slots = []
    for start_s, end_s in TIME_SLOT_RANGES:
        slots.append((start_s, end_s, parse_time(start_s), parse_time(end_s)))
    return slots

def apply_stock_delta(material: Material, old_delivered: int, old_returned: int, new_delivered: int, new_returned: int):
    old_outstanding = old_delivered - old_returned
    new_outstanding = new_delivered - new_returned
    delta_outstanding = new_outstanding - old_outstanding

    current_available = material.pieces_qty if material.pieces_qty is not None else 0
    new_available = current_available - delta_outstanding

    if new_available < 0:
        raise ValueError(f"Stock insuficiente para {material.name}")

    material.pieces_qty = new_available

def build_week_schedule(week_days, selected_room=None):
    week_start = week_days[0]
    week_end = week_days[-1]

    q = (
        Reservation.query
        .filter(Reservation.status.in_([ReservationStatus.APPROVED, ReservationStatus.PENDING]))
        .filter(Reservation.date >= week_start)
        .filter(Reservation.date <= week_end)
    )

    if selected_room:
        q = q.filter(Reservation.room == selected_room)
        room_list = [selected_room]
    else:
        room_list = list(ROOMS)

    reservations = q.order_by(
        Reservation.room.asc(),
        Reservation.date.asc(),
        Reservation.start_time.asc()
    ).options(
        joinedload(Reservation.user)
    ).all()

    schedule = {
        room: {
            day: {"items": [], "slots": []}
            for day in week_days
        }
        for room in room_list
    }

    for r in reservations:
        if r.room in schedule and r.date in schedule[r.room]:
            schedule[r.room][r.date]["items"].append(r)

    now = datetime.now()
    today = now.date()
    now_time = now.time()
    base_slots = _build_time_slots()

    for room in room_list:
        for day in week_days:
            cell = schedule[room][day]
            items = cell["items"]
            slot_rows = []
            for start_label, end_label, slot_start, slot_end in base_slots:
                overlapping = [
                    item for item in items
                    if item.start_time < slot_end and item.end_time > slot_start
                ]

                if not overlapping:
                    state = "available"
                elif any((item.status or "").upper() == ReservationStatus.PENDING for item in overlapping):
                    state = "pending"
                elif day == today and any(
                    (item.status or "").upper() == ReservationStatus.APPROVED and item.start_time <= now_time < item.end_time
                    for item in overlapping
                ):
                    state = "in_progress"
                else:
                    state = "occupied"

                slot_rows.append({
                    "start": start_label,
                    "end": end_label,
                    "state": state,
                })

            cell["slots"] = slot_rows

    return schedule, room_list


@reservations_bp.route("/", methods=["GET"])
@min_role_required("STUDENT")
def reservations_home():
    if is_admin_role(current_user.role):
        return redirect(url_for("reservations.admin_queue"))

    return redirect(url_for("reservations.my_reservations"))


@reservations_bp.route("/my", methods=["GET"])
@min_role_required("STUDENT")
def my_reservations():
    reservations = (
        Reservation.query
        .options(
            joinedload(Reservation.items).joinedload(ReservationItem.material),
            joinedload(Reservation.lab_tickets),
            joinedload(Reservation.user)
        )
        .filter(Reservation.user_id == current_user.id)
        .order_by(Reservation.created_at.desc())
        .all()
    )

    return render_template(
        "reservations/my_reservations.html",
        reservations=reservations,
        active_page="reservations"
    )


@reservations_bp.route("/my/<int:reservation_id>/ticket", methods=["GET", "POST"])
@min_role_required("STUDENT")
def my_active_ticket(reservation_id: int):
    reservation = (
        Reservation.query
        .options(
            joinedload(Reservation.lab_tickets).joinedload(LabTicket.items).joinedload(TicketItem.material),
            joinedload(Reservation.user),
        )
        .filter(Reservation.id == reservation_id, Reservation.user_id == current_user.id)
        .first()
    )
    if not reservation:
        flash("Reserva no encontrada.", "error")
        return redirect(url_for("reservations.my_reservations"))

    ticket = next(
        (
            t for t in reservation.lab_tickets
            if _is_active_ticket_status(t.status) or _is_ticket_closure_requested(t.status)
        ),
        None,
    )
    if not ticket:
        flash("No tienes ticket activo para esta reserva.", "warning")
        return redirect(url_for("reservations.my_reservations"))

    if request.method == "POST":
        active_result = validate_ticket_active(ticket)
        if not active_result.ok:
            flash(active_result.message or "No se pueden agregar materiales a un ticket cerrado.", "error")
            return redirect(url_for("reservations.my_active_ticket", reservation_id=reservation.id))

        material_id = request.form.get("material_id", type=int)
        quantity = request.form.get("quantity", type=int)

        if not material_id or not quantity or quantity <= 0:
            flash("Selecciona material y una cantidad válida.", "error")
            return redirect(url_for("reservations.my_active_ticket", reservation_id=reservation.id))

        material = Material.query.get(material_id)
        if not material:
            flash("Material no encontrado.", "error")
            return redirect(url_for("reservations.my_active_ticket", reservation_id=reservation.id))
        if _is_inactive_status(material.status):
            flash("El material seleccionado no está activo para solicitudes.", "error")
            return redirect(url_for("reservations.my_active_ticket", reservation_id=reservation.id))

        if _is_student_role(current_user.role) and material.career_id != current_user.career_id:
            flash("No puedes solicitar materiales de otra carrera.", "error")
            return redirect(url_for("reservations.my_active_ticket", reservation_id=reservation.id))

        result = add_material_to_ticket(
            ticket=ticket,
            material=material,
            quantity=quantity,
            actor_user=current_user,
        )
        if not result.ok:
            flash(result.message, "error")
            return redirect(url_for("reservations.my_active_ticket", reservation_id=reservation.id))

        for notif in result.data.get("notifications", []):
            publish_notification_created(notif)

        flash("Material agregado al ticket activo. El admin fue notificado.", "success")
        return redirect(url_for("reservations.my_active_ticket", reservation_id=reservation.id))

    available_materials = (
        _exclude_inactive_materials(Material.query)
        .filter(Material.career_id == current_user.career_id if _is_student_role(current_user.role) else True)
        .order_by(Material.name.asc())
        .all()
    )

    return render_template(
        "reservations/my_ticket.html",
        reservation=reservation,
        ticket=ticket,
        materials=available_materials,
        active_page="reservations",
    )


@reservations_bp.route("/my/tickets/<int:ticket_id>/request-close", methods=["POST"])
@min_role_required("STUDENT")
def my_ticket_request_close(ticket_id: int):
    ticket = (
        LabTicket.query
        .options(joinedload(LabTicket.reservation))
        .filter(LabTicket.id == ticket_id, LabTicket.owner_user_id == current_user.id)
        .first()
    )
    if not ticket:
        flash("Ticket no encontrado.", "error")
        return redirect(url_for("reservations.my_reservations"))

    result = request_ticket_closure(ticket=ticket, actor_user=current_user)
    if not result.ok:
        flash(result.message, "warning")
        return redirect(url_for("reservations.my_active_ticket", reservation_id=ticket.reservation_id))

    for notif in result.data.get("notifications", []):
        publish_notification_created(notif)

    flash("Solicitud de cierre enviada. Espera confirmación del administrador.", "success")
    return redirect(url_for("reservations.my_active_ticket", reservation_id=ticket.reservation_id))


@reservations_bp.route("/request", methods=["GET", "POST"])
@min_role_required("STUDENT")
def request_reservation():
    if user_has_open_debts(current_user.id):
        flash("Tienes un adeudo activo. No puedes solicitar reservas.", "error")
        return redirect(url_for("reservations.my_reservations"))

    week_start_s = (request.args.get("week_start") or "").strip()
    calendar_room = (request.args.get("calendar_room") or "").strip()

    try:
        base_date = parse_date(week_start_s) if week_start_s else datetime.today().date()
    except ValueError:
        base_date = datetime.today().date()

    week_start = get_week_start(base_date)
    week_days = build_week_days(week_start)
    week_end = week_days[-1]

    selected_calendar_room = calendar_room if calendar_room in ROOMS else ""
    week_schedule, calendar_rooms = build_week_schedule(
        week_days=week_days,
        selected_room=selected_calendar_room or None
    )

    prev_week = week_start - timedelta(days=7)
    next_week = week_start + timedelta(days=7)

    is_professor = _is_professor_role(current_user.role)
    assignments = _professor_assignments(current_user.id) if is_professor else []
    professor_subjects = sorted({a.subject.name for a in assignments if a.subject})
    professor_groups_by_subject = {}
    for assignment in assignments:
        if not assignment.subject:
            continue
        professor_groups_by_subject.setdefault(assignment.subject.name, set()).add(assignment.group_code)
    professor_groups_by_subject = {
        subject_name: sorted(groups)
        for subject_name, groups in professor_groups_by_subject.items()
    }
    if request.method == "POST":
        room = (request.form.get("room") or "").strip()
        date_s = (request.form.get("date") or "").strip()
        start_s = (request.form.get("start_time") or "").strip()
        end_s = (request.form.get("end_time") or "").strip()
        purpose = (request.form.get("purpose") or "").strip()
        group_name = (request.form.get("group_name") or "").strip()
        requester_name = _build_requester_name()
        subject = (request.form.get("subject") or "").strip()
        signature_data = request.form.get("signature_data") or ""
        selected_subject_id = None

        group_name, group_error = normalize_and_validate_group_code(group_name)
        if group_error:
            flash(group_error, "error")
            return redirect(url_for("reservations.request_reservation"))

        if is_professor:
            if not assignments:
                flash("No tienes materias asignadas. Completa tu perfil o solicita actualización de materias.", "error")
                return redirect(url_for("reservations.request_reservation"))

            valid_assignment = next(
                (a for a in assignments if a.subject and a.subject.name.lower() == subject.lower() and a.group_code == group_name),
                None,
            )
            if not valid_assignment:
                flash("La materia/grupo seleccionados no pertenecen a tu carga académica.", "error")
                return redirect(url_for("reservations.request_reservation"))
            subject = valid_assignment.subject.name
            selected_subject_id = valid_assignment.subject.id

        if (
            not room
            or not date_s
            or not start_s
            or not end_s
            or not group_name
            or not subject
        ):
            flash("Faltan datos obligatorios.", "error")
            return redirect(url_for("reservations.request_reservation"))

        if not selected_subject_id:
            matched_subject = Subject.query.filter(func.lower(Subject.name) == subject.lower()).first()
            if matched_subject:
                selected_subject_id = matched_subject.id

        try:
            date_ = parse_date(date_s)
            start_t = parse_time(start_s)
            end_t = parse_time(end_s)
        except ValueError:
            flash("Formato de fecha u hora inválido.", "error")
            return redirect(url_for("reservations.request_reservation"))

        if end_t <= start_t:
            flash("La hora final debe ser mayor a la hora inicial.", "error")
            return redirect(url_for("reservations.request_reservation"))

        allowed_start_time = parse_time("08:00")
        allowed_end_time = parse_time("21:00")
        if start_t < allowed_start_time or end_t > allowed_end_time:
            flash("Las reservaciones solo están permitidas entre 08:00 y 21:00.", "error")
            return redirect(url_for("reservations.request_reservation"))

        minutes = duration_minutes(start_t, end_t)
        if minutes > 120:
            flash("La duración máxima permitida es de 2 horas.", "error")
            return redirect(url_for("reservations.request_reservation"))

        if overlaps(room, date_, start_t, end_t):
            flash("Ya existe una reserva aprobada que se empalma con ese horario.", "error")
            return redirect(url_for("reservations.request_reservation"))

        signature_ref, signature_error = _save_signature_image(signature_data)
        if signature_error:
            flash(signature_error, "error")
            return redirect(url_for("reservations.request_reservation"))

        r = Reservation(
            user_id=current_user.id,
            room=room,
            date=date_,
            start_time=start_t,
            end_time=end_t,
            purpose=purpose or None,
            group_name=group_name,
            teacher_name=requester_name,
            subject=subject,
            subject_id=selected_subject_id,
            signed=bool(signature_ref),
            signature_ref=signature_ref,
            status=ReservationStatus.PENDING,
        )

        db.session.add(r)
        db.session.flush()

        material_ids = request.form.getlist("material_id[]")
        quantities = request.form.getlist("quantity[]")

        for i in range(len(material_ids)):
            try:
                material_id = int(material_ids[i])
                qty = int(quantities[i])
            except (ValueError, IndexError):
                continue

            if qty <= 0:
                continue

            material = Material.query.get(material_id)
            if not material:
                continue
            if _is_inactive_status(material.status):
                db.session.rollback()
                flash(f"{material.name}: está inactivo y no se puede solicitar.", "error")
                return redirect(url_for("reservations.request_reservation"))
            if _is_student_role(current_user.role) and material.career_id != current_user.career_id:
                db.session.rollback()
                flash(f"{material.name}: no pertenece a tu carrera.", "error")
                return redirect(url_for("reservations.request_reservation"))

            if material.pieces_qty is not None and qty > material.pieces_qty:
                db.session.rollback()
                flash(f"{material.name}: solo hay {material.pieces_qty} disponibles", "error")
                return redirect(url_for("reservations.request_reservation"))

            item = ReservationItem(
                reservation_id=r.id,
                material_id=material_id,
                quantity_requested=qty
            )
            db.session.add(item)

        admins = User.query.filter(User.role.in_(["ADMIN", "SUPERADMIN"])).all()
        admin_notifications: list[Notification] = []

        for admin in admins:
            notif = Notification(
                user_id=admin.id,
                title="Nueva reserva pendiente",
                message=f"El usuario {current_user.email} creó la reserva #{r.id} para {room} el {date_}.",
                link="/reservations/admin"
            )
            db.session.add(notif)
            admin_notifications.append(notif)

        log_event(
            module="RESERVATIONS",
            action="RESERVATION_CREATED",
            user_id=current_user.id,
            entity_label=f"Reservation #{r.id}",
            description=f"Reserva creada para {room} {date_} {start_t}-{end_t}",
            metadata={"reservation_id": r.id, "room": room, "status": ReservationStatus.PENDING},
        )

        db.session.commit()
        for notification in admin_notifications:
            try:
                publish_notification_created(notification)
            except Exception:
                logger.warning(
                    "SSE publish failed after reservation request",
                    extra={"reservation_id": r.id, "notification_id": notification.id, "target_user_id": notification.user_id},
                )

        flash("Solicitud enviada. Queda pendiente de aprobación.", "success")
        return redirect(url_for("reservations.my_reservations"))

    materials = (
        _exclude_inactive_materials(Material.query)
        .filter(Material.career_id == current_user.career_id if _is_student_role(current_user.role) else True)
        .order_by(Material.name.asc())
        .all()
    )
    materials_json = json.dumps([
        {
            "id": m.id,
            "name": m.name,
            "pieces_qty": m.pieces_qty if m.pieces_qty is not None else 0
        }
        for m in materials
    ])

    return render_template(
        "reservations/request.html",
    rooms=ROOMS,
    materials=materials,
    materials_json=materials_json,
    week_days=week_days,
    week_start=week_start,
    week_end=week_end,
    week_schedule=week_schedule,
    calendar_rooms=calendar_rooms,
    selected_calendar_room=selected_calendar_room,
    prev_week=prev_week,
    next_week=next_week,
    is_professor=is_professor,
    professor_subjects=professor_subjects,
    professor_groups_by_subject=professor_groups_by_subject,
    active_page="reservations"
)

@reservations_bp.route("/admin", methods=["GET"])
@min_role_required("ADMIN")
def admin_queue():
    pending = (
        Reservation.query
        .options(
            joinedload(Reservation.items).joinedload(ReservationItem.material),
            joinedload(Reservation.user)
        )
        .filter(Reservation.status == ReservationStatus.PENDING)
        .order_by(Reservation.created_at.asc())
        .all()
    )
    return render_template(
        "reservations/admin_queue.html",
        reservations=pending,
        active_page="reservations"
    )


@reservations_bp.route("/admin/approved", methods=["GET"])
@min_role_required("ADMIN")
def admin_approved():
    now = datetime.now()
    today = now.date()
    current_time = now.time()

    approved = (
        Reservation.query
        .options(
            joinedload(Reservation.items).joinedload(ReservationItem.material),
            joinedload(Reservation.lab_tickets),
            joinedload(Reservation.user)
        )
        .filter(Reservation.status == ReservationStatus.APPROVED)
        .filter(Reservation.date == today)
        .order_by(Reservation.start_time.asc())
        .all()
    )

    for r in approved:
        open_ticket = next((t for t in r.lab_tickets if (t.status or "").upper() in BLOCKING_LAB_TICKET_STATUSES), None)
        r.open_ticket = open_ticket

        if open_ticket:
            r.can_open_ticket = False
            r.open_ticket_reason = "active"
            continue

        open_window_start = (datetime.combine(r.date, r.start_time) - timedelta(minutes=30)).time()
        open_window_end = r.end_time

        if current_time < open_window_start:
            r.can_open_ticket = False
            r.open_ticket_reason = "too_early"
        elif current_time > open_window_end:
            r.can_open_ticket = False
            r.open_ticket_reason = "expired"
        else:
            r.can_open_ticket = True
            r.open_ticket_reason = "available"

    return render_template(
        "reservations/admin_approved.html",
        reservations=approved,
        active_page="reservations"
    )


@reservations_bp.route("/admin/tickets/closure-requests", methods=["GET"])
@min_role_required("ADMIN")
def admin_ticket_closure_requests():
    tickets = (
        LabTicket.query
        .options(
            joinedload(LabTicket.owner_user),
            joinedload(LabTicket.reservation),
            joinedload(LabTicket.items).joinedload(TicketItem.material),
        )
        .filter(LabTicket.status == LabTicketStatus.CLOSURE_REQUESTED)
        .order_by(LabTicket.opened_at.asc())
        .all()
    )
    return render_template(
        "reservations/admin_ticket_closure_requests.html",
        tickets=tickets,
        active_page="reservations",
    )

@reservations_bp.route("/admin/approved/history", methods=["GET"])
@min_role_required("ADMIN")
def admin_approved_history():
    today = datetime.now().date()

    reservations = (
        Reservation.query
        .options(
            joinedload(Reservation.items).joinedload(ReservationItem.material),
            joinedload(Reservation.lab_tickets),
            joinedload(Reservation.user)
        )
        .filter(Reservation.status == ReservationStatus.APPROVED)
        .filter(Reservation.date < today)
        .order_by(Reservation.date.desc(), Reservation.start_time.desc())
        .all()
    )

    return render_template(
        "reservations/admin_approved_history.html",
        reservations=reservations,
        active_page="reservations"
    )

@reservations_bp.route("/admin/<int:res_id>/approve", methods=["POST"])
@min_role_required("ADMIN")
def admin_approve(res_id: int):
    r = Reservation.query.get(res_id)

    if not r:
        flash("Reserva no encontrada.", "error")
        return redirect(url_for("reservations.admin_queue"))

    if r.status == ReservationStatus.APPROVED:
        log_event(
            module="RESERVATIONS",
            action="RESERVATION_APPROVE_REJECTED",
            user_id=current_user.id,
            entity_label=f"Reservation #{r.id}",
            description="Intento inválido de aprobar reservación ya aprobada",
            metadata={"reservation_id": r.id, "entity_id": r.id, "result": "rejected", "reason": "already_approved"},
        )
        flash("La reservación ya fue aprobada.", "warning")
        return redirect(url_for("reservations.admin_queue"))
    if r.status == ReservationStatus.REJECTED:
        log_event(
            module="RESERVATIONS",
            action="RESERVATION_APPROVE_REJECTED",
            user_id=current_user.id,
            entity_label=f"Reservation #{r.id}",
            description="Intento inválido de aprobar reservación ya rechazada",
            metadata={"reservation_id": r.id, "entity_id": r.id, "result": "rejected", "reason": "already_rejected"},
        )
        flash("La reservación ya fue rechazada.", "warning")
        return redirect(url_for("reservations.admin_queue"))
    if r.status != ReservationStatus.PENDING:
        log_event(
            module="RESERVATIONS",
            action="RESERVATION_APPROVE_REJECTED",
            user_id=current_user.id,
            entity_label=f"Reservation #{r.id}",
            description="Intento inválido de aprobar reservación en estado no permitido",
            metadata={"reservation_id": r.id, "entity_id": r.id, "result": "rejected", "reason": f"invalid_status:{r.status}"},
        )
        flash(f"La reservación no se puede aprobar desde estado {r.status}.", "error")
        return redirect(url_for("reservations.admin_queue"))

    if overlaps(r.room, r.date, r.start_time, r.end_time):
        flash("No se puede aprobar: se empalma con otra reserva aprobada.", "error")
        return redirect(url_for("reservations.admin_queue"))

    approval_notification = approve_reservation(
        reservation=r,
        admin_user=current_user,
        admin_note=request.form.get("admin_note"),
    )
    publish_notification_created(approval_notification)

    flash("Reserva aprobada.", "success")
    return redirect(url_for("reservations.admin_queue"))


@reservations_bp.route("/admin/<int:res_id>/reject", methods=["POST"])
@min_role_required("ADMIN")
def admin_reject(res_id: int):
    r = Reservation.query.get(res_id)
    if not r:
        flash("Reserva no encontrada.", "error")
        return redirect(url_for("reservations.admin_queue"))

    if r.status == ReservationStatus.REJECTED:
        log_event(
            module="RESERVATIONS",
            action="RESERVATION_REJECT_REJECTED",
            user_id=current_user.id,
            entity_label=f"Reservation #{r.id}",
            description="Intento inválido de rechazar reservación ya rechazada",
            metadata={"reservation_id": r.id, "entity_id": r.id, "result": "rejected", "reason": "already_rejected"},
        )
        flash("La reservación ya fue rechazada.", "warning")
        return redirect(url_for("reservations.admin_queue"))
    if r.status == ReservationStatus.APPROVED:
        log_event(
            module="RESERVATIONS",
            action="RESERVATION_REJECT_REJECTED",
            user_id=current_user.id,
            entity_label=f"Reservation #{r.id}",
            description="Intento inválido de rechazar reservación ya aprobada",
            metadata={"reservation_id": r.id, "entity_id": r.id, "result": "rejected", "reason": "already_approved"},
        )
        flash("La reservación ya fue aprobada y no se puede rechazar.", "warning")
        return redirect(url_for("reservations.admin_queue"))
    if r.status != ReservationStatus.PENDING:
        log_event(
            module="RESERVATIONS",
            action="RESERVATION_REJECT_REJECTED",
            user_id=current_user.id,
            entity_label=f"Reservation #{r.id}",
            description="Intento inválido de rechazar reservación en estado no permitido",
            metadata={"reservation_id": r.id, "entity_id": r.id, "result": "rejected", "reason": f"invalid_status:{r.status}"},
        )
        flash(f"La reservación no se puede rechazar desde estado {r.status}.", "error")
        return redirect(url_for("reservations.admin_queue"))

    rejection_notification = reject_reservation(
        reservation=r,
        admin_user=current_user,
        admin_note=request.form.get("admin_note"),
    )
    publish_notification_created(rejection_notification)

    flash("Reserva rechazada.", "success")
    return redirect(url_for("reservations.admin_queue"))


@reservations_bp.route("/admin/<int:res_id>/open-ticket", methods=["POST"])
@min_role_required("ADMIN")
def admin_open_ticket(res_id: int):
    r = Reservation.query.get(res_id)
    if not r:
        flash("Reserva no encontrada.", "error")
        return redirect(url_for("reservations.admin_approved"))

    if r.status != ReservationStatus.APPROVED:
        flash("Solo se puede abrir ticket para reservas aprobadas.", "error")
        return redirect(url_for("reservations.admin_approved"))

    existing_ticket = (
        LabTicket.query
        .filter(LabTicket.reservation_id == r.id)
        .filter(LabTicket.status.in_(list(BLOCKING_LAB_TICKET_STATUSES)))
        .first()
    )
    if existing_ticket:
        flash("Ya existe un ticket activo para esta reserva.", "error")
        return redirect(url_for("reservations.admin_approved"))

    now = datetime.now()
    today = now.date()
    current_time = now.time()

    if r.date != today:
        flash("Solo se puede abrir ticket para reservas del día actual.", "error")
        return redirect(url_for("reservations.admin_approved"))

    open_window_start = (datetime.combine(r.date, r.start_time) - timedelta(minutes=30)).time()
    open_window_end = r.end_time

    if current_time < open_window_start or current_time > open_window_end:
        flash("El ticket solo puede abrirse dentro de la ventana válida de uso.", "error")
        return redirect(url_for("reservations.admin_approved"))

    ticket = LabTicket(
        reservation_id=r.id,
        owner_user_id=r.user_id,
        room=r.room,
        date=r.date,
        status=LabTicketStatus.OPEN,
        opened_by_user_id=current_user.id,
        notes=f"Ticket generado desde reserva #{r.id}"
    )

    db.session.add(ticket)
    db.session.flush()

    log_event(
        module="LAB_TICKETS",
        action="LAB_TICKET_OPENED",
        user_id=current_user.id,
        entity_label=f"LabTicket #{ticket.id}",
        description=f"Ticket abierto desde reserva #{r.id}",
        metadata={"ticket_id": ticket.id, "reservation_id": r.id, "owner_user_id": r.user_id},
    )

    for reservation_item in r.items:
        ticket_item = TicketItem(
            ticket_id=ticket.id,
            material_id=reservation_item.material_id,
            quantity_requested=reservation_item.quantity_requested,
            quantity_delivered=0,
            quantity_returned=0,
            status=TicketItemStatus.REQUESTED
        )
        db.session.add(ticket_item)

    ticket_opened_notification = Notification(
        user_id=r.user_id,
        title="Ticket de laboratorio abierto",
        message=f"Se abrió el ticket de tu reservación #{r.id}.",
        link=url_for("reservations.my_active_ticket", reservation_id=r.id),
    )
    db.session.add(ticket_opened_notification)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        flash("No se pudo abrir el ticket por una operación concurrente. Intenta recargar la página.", "warning")
        return redirect(url_for("reservations.admin_approved"))
    publish_notification_created(ticket_opened_notification)

    flash("Ticket de laboratorio abierto correctamente.", "success")
    return redirect(url_for("reservations.admin_approved"))

@reservations_bp.route("/admin/tickets/<int:ticket_id>", methods=["GET"])
@min_role_required("ADMIN")
def admin_ticket_detail(ticket_id: int):
    ticket = (
        LabTicket.query
        .options(joinedload(LabTicket.items).joinedload(TicketItem.material))
        .filter(LabTicket.id == ticket_id)
        .first()
    )

    if not ticket:
        flash("Ticket no encontrado.", "error")
        return redirect(url_for("reservations.admin_approved"))

    return render_template(
        "reservations/ticket_detail.html",
        ticket=ticket,
        active_page="reservations"
    )


@reservations_bp.route("/admin/tickets/items/<int:item_id>/update", methods=["POST"])
@min_role_required("ADMIN")
def admin_ticket_item_update(item_id: int):
    item = TicketItem.query.get(item_id)
    if not item:
        flash("Ítem del ticket no encontrado.", "error")
        return redirect(url_for("reservations.admin_approved"))
    if not item.ticket:
        flash("El ticket asociado al ítem no existe.", "error")
        return redirect(url_for("reservations.admin_approved"))
    if not _is_ticket_operable_for_item_updates(item.ticket.status):
        flash("No se pueden actualizar materiales de un ticket cerrado.", "error")
        return redirect(url_for("reservations.admin_ticket_detail", ticket_id=item.ticket_id))

    try:
        delivered = int(request.form.get("quantity_delivered") or 0)
        returned = int(request.form.get("quantity_returned") or 0)
    except ValueError:
        flash("Las cantidades deben ser números válidos.", "error")
        return redirect(url_for("reservations.admin_ticket_detail", ticket_id=item.ticket_id))

    if delivered < 0 or returned < 0:
        flash("Las cantidades no pueden ser negativas.", "error")
        return redirect(url_for("reservations.admin_ticket_detail", ticket_id=item.ticket_id))

    if delivered > item.quantity_requested:
        flash("No puedes entregar más de lo solicitado.", "error")
        return redirect(url_for("reservations.admin_ticket_detail", ticket_id=item.ticket_id))

    if returned > delivered:
        flash("No puedes devolver más de lo entregado.", "error")
        return redirect(url_for("reservations.admin_ticket_detail", ticket_id=item.ticket_id))

    material = item.material
    if not material:
        flash("Material no encontrado.", "error")
        return redirect(url_for("reservations.admin_ticket_detail", ticket_id=item.ticket_id))

    try:
        apply_stock_delta(
            material=material,
            old_delivered=item.quantity_delivered,
            old_returned=item.quantity_returned,
            new_delivered=delivered,
            new_returned=returned
        )
    except ValueError:
        flash(f"Stock insuficiente para {material.name}. Disponibles actuales: {material.pieces_qty}.", "error")
        return redirect(url_for("reservations.admin_ticket_detail", ticket_id=item.ticket_id))

    item.quantity_delivered = delivered
    item.quantity_returned = returned
    item.notes = (request.form.get("notes") or "").strip() or None

    apply_ticket_item_status(item=item, delivered=delivered, returned=returned)

    _sync_ticket_ready_status(item.ticket)
    owner_notification = Notification(
        user_id=item.ticket.owner_user_id,
        title="Ticket de reservación actualizado",
        message=f"Se actualizó un material en tu ticket #{item.ticket_id}.",
        link=url_for("reservations.my_active_ticket", reservation_id=item.ticket.reservation_id) if item.ticket and item.ticket.reservation_id else url_for("reservations.my_reservations"),
    )
    db.session.add(owner_notification)
    db.session.commit()
    publish_notification_created(owner_notification)

    flash("Ítem del ticket actualizado.", "success")
    return redirect(url_for("reservations.admin_ticket_detail", ticket_id=item.ticket_id))


@reservations_bp.route("/admin/tickets/items/<int:item_id>/ready", methods=["POST"])
@min_role_required("ADMIN")
def admin_ticket_item_mark_ready(item_id: int):
    item = TicketItem.query.get(item_id)
    if not item:
        flash("Ítem del ticket no encontrado.", "error")
        return redirect(url_for("reservations.admin_approved"))

    ticket = item.ticket
    if not ticket or not _is_active_ticket_status(ticket.status):
        flash("Solo puedes marcar como listo materiales de tickets activos.", "error")
        return redirect(url_for("reservations.admin_approved"))

    if item.quantity_requested <= item.quantity_delivered:
        flash("No hay pendientes por preparar en este material.", "warning")
        return redirect(url_for("reservations.admin_ticket_detail", ticket_id=ticket.id))

    if ticket.status == LabTicketStatus.READY_FOR_PICKUP:
        flash("Este material ya está marcado como listo para recoger.", "warning")
        return redirect(url_for("reservations.admin_ticket_detail", ticket_id=ticket.id))

    if item.status == TicketItemStatus.RETURNED:
        flash("No se puede marcar como listo un material ya devuelto.", "error")
        return redirect(url_for("reservations.admin_ticket_detail", ticket_id=ticket.id))

    item.status = TicketItemStatus.PENDING
    ticket.status = LabTicketStatus.READY_FOR_PICKUP

    notif = Notification(
        user_id=ticket.owner_user_id,
        title="Material listo para recoger",
        message=f"Hay material listo para recoger en tu ticket #{ticket.id}.",
        link=url_for("reservations.my_active_ticket", reservation_id=ticket.reservation_id) if ticket.reservation_id else url_for("reservations.my_reservations"),
    )
    db.session.add(notif)
    db.session.commit()
    publish_notification_created(notif)

    flash("Material marcado como listo para recoger.", "success")
    return redirect(url_for("reservations.admin_ticket_detail", ticket_id=ticket.id))


@reservations_bp.route("/admin/tickets/<int:ticket_id>/close", methods=["POST"])
@min_role_required("ADMIN")
def admin_ticket_close(ticket_id: int):
    ticket = (
        LabTicket.query
        .options(joinedload(LabTicket.items).joinedload(TicketItem.material))
        .filter(LabTicket.id == ticket_id)
        .first()
    )

    if not ticket:
        flash("Ticket no encontrado.", "error")
        return redirect(url_for("reservations.admin_approved"))

    result = close_ticket(ticket=ticket, actor_user=current_user)
    if not result.ok:
        flash(result.message, "error")
        return redirect(url_for("reservations.admin_ticket_detail", ticket_id=ticket.id))

    close_notification = result.data["close_notification"]
    admin_notifications = result.data["admin_notifications"]

    publish_notification_created(close_notification)
    for notif in admin_notifications:
        publish_notification_created(notif)

    flash("Ticket cerrado correctamente.", "success")
    return redirect(url_for("reservations.admin_ticket_detail", ticket_id=ticket.id))

@reservations_bp.route("/admin/tickets/<int:ticket_id>/update-all", methods=["POST"])
@min_role_required("ADMIN")
def admin_ticket_update_all(ticket_id: int):
    ticket = LabTicket.query.get(ticket_id)
    if not ticket:
        flash("Ticket no encontrado.", "error")
        return redirect(url_for("reservations.admin_approved"))
    if not _is_ticket_operable_for_item_updates(ticket.status):
        flash("No se pueden actualizar materiales de un ticket cerrado.", "error")
        return redirect(url_for("reservations.admin_ticket_detail", ticket_id=ticket_id))

    item_ids = request.form.getlist("item_id[]")
    delivered_list = request.form.getlist("quantity_delivered[]")
    returned_list = request.form.getlist("quantity_returned[]")
    notes_list = request.form.getlist("notes[]")

    try:
        for i in range(len(item_ids)):
            try:
                item_id = int(item_ids[i])
                delivered = int(delivered_list[i] or 0)
                returned = int(returned_list[i])
            except (ValueError, IndexError):
                continue

            item = TicketItem.query.get(item_id)
            if not item:
                continue
            if item.ticket_id != ticket_id:
                flash("Se detectó un ítem que no pertenece a este ticket.", "error")
                db.session.rollback()
                return redirect(url_for("reservations.admin_ticket_detail", ticket_id=ticket_id))

            if delivered < 0 or returned < 0:
                flash("Las cantidades no pueden ser negativas.", "error")
                db.session.rollback()
                return redirect(url_for("reservations.admin_ticket_detail", ticket_id=ticket_id))

            if delivered > item.quantity_requested:
                flash(f"No puedes entregar más de lo solicitado en {item.material.name if item.material else 'el material'}.", "error")
                db.session.rollback()
                return redirect(url_for("reservations.admin_ticket_detail", ticket_id=ticket_id))

            if returned > delivered:
                flash(f"No puedes devolver más de lo entregado en {item.material.name if item.material else 'el material'}.", "error")
                db.session.rollback()
                return redirect(url_for("reservations.admin_ticket_detail", ticket_id=ticket_id))

            material = item.material
            if not material:
                flash("Uno de los materiales del ticket no existe.", "error")
                db.session.rollback()
                return redirect(url_for("reservations.admin_ticket_detail", ticket_id=ticket_id))

            old_delivered = item.quantity_delivered
            old_returned = item.quantity_returned

            try:
                apply_stock_delta(
                    material=material,
                    old_delivered=old_delivered,
                    old_returned=old_returned,
                    new_delivered=delivered,
                    new_returned=returned
                )
            except ValueError:
                flash(f"Stock insuficiente para {material.name}. Disponibles actuales: {material.pieces_qty}.", "error")
                db.session.rollback()
                return redirect(url_for("reservations.admin_ticket_detail", ticket_id=ticket_id))

            item.quantity_delivered = delivered
            item.quantity_returned = returned
            item.notes = (notes_list[i] or "").strip() or None

            apply_ticket_item_status(item=item, delivered=delivered, returned=returned)

        _sync_ticket_ready_status(ticket)
        bulk_update_notification = Notification(
            user_id=ticket.owner_user_id,
            title="Ticket de reservación actualizado",
            message=f"Se actualizaron los materiales del ticket #{ticket_id}.",
            link=url_for("reservations.my_active_ticket", reservation_id=ticket.reservation_id) if ticket.reservation_id else url_for("reservations.my_reservations"),
        )
        db.session.add(bulk_update_notification)
        db.session.commit()
        publish_notification_created(bulk_update_notification)
        flash("Todos los materiales actualizados correctamente.", "success")
        return redirect(url_for("reservations.admin_ticket_detail", ticket_id=ticket_id))

    except Exception:
        db.session.rollback()
        flash("No se pudieron actualizar los materiales del ticket.", "error")
        return redirect(url_for("reservations.admin_ticket_detail", ticket_id=ticket_id))
