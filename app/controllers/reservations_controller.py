import logging
import os
import base64
import binascii
from datetime import datetime, timedelta
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
from app.models.subject import Subject
from app.models.teacher_academic_load import TeacherAcademicLoad
from app.models.user import User

from app.extensions import db
from app.models.reservation import Reservation
from app.services.audit_service import log_event
from app.services.debt_service import user_has_open_debts
from app.services.notification_service import (
    build_reservation_message,
    notify_roles,
    publish_notifications_safe,
)
from app.services.reservation_service import approve_reservation, reject_reservation, expire_unapproved_reservations
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
from app.utils.media import resolve_media_url
from app.constants import ROOMS
from app.utils.text import lab_room_code_variants, normalize_lab_room_code

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


def _assignment_subject_name(assignment: TeacherAcademicLoad) -> str:
    manual_name = (assignment.subject_name or "").strip().upper()
    if manual_name:
        return manual_name
    if assignment.subject and assignment.subject.name:
        return assignment.subject.name.strip().upper()
    return ""


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
    if not raw:
        return None, "Debes guardar tu firma digital antes de enviar."
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
    if not payload.startswith(b"\x89PNG\r\n\x1a\n"):
        return None, "El formato de firma no es válido."

    uploads_rel_dir = os.path.join("uploads", "signatures")
    uploads_abs_dir = os.path.join(current_app.root_path, "static", uploads_rel_dir)
    os.makedirs(uploads_abs_dir, exist_ok=True)

    filename = f"{uuid4().hex}.png"
    abs_path = os.path.join(uploads_abs_dir, filename)
    with open(abs_path, "wb") as fp:
        fp.write(payload)

    return f"{uploads_rel_dir}/{filename}", None


def _signature_asset_url(signature_ref: str | None) -> str | None:
    return resolve_media_url(signature_ref, ensure_static_file=True)


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
    room_variants = lab_room_code_variants(room)
    q = (
        Reservation.query
        .filter(Reservation.room.in_(room_variants) if room_variants else Reservation.room == room)
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



def _format_ampm(time_value) -> str:
    return datetime.combine(datetime.today(), time_value).strftime("%I:%M %p").lstrip("0")


def _build_time_slots() -> list[tuple[str, str, object, object]]:
    slots = []
    for hour in range(8, 21):
        start_s = f"{hour:02d}:00"
        end_s = f"{hour + 1:02d}:00"
        slots.append((start_s, end_s, parse_time(start_s), parse_time(end_s)))
    return slots


def _room_building(room: str | None) -> str:
    value = normalize_lab_room_code(room)
    return value[:1] if value else ""


def _rooms_by_building(building: str | None) -> list[str]:
    normalized = (building or "").strip().upper()
    if not normalized:
        return list(ROOMS)
    return [room for room in ROOMS if _room_building(room) == normalized]

def apply_stock_delta(material: Material, old_delivered: int, old_returned: int, new_delivered: int, new_returned: int):
    old_outstanding = old_delivered - old_returned
    new_outstanding = new_delivered - new_returned
    delta_outstanding = new_outstanding - old_outstanding

    current_available = material.pieces_qty if material.pieces_qty is not None else 0
    new_available = current_available - delta_outstanding

    if new_available < 0:
        raise ValueError(f"Stock insuficiente para {material.name}")

    material.pieces_qty = new_available

def _compute_slot_state(day, slot_end, overlapping, now_dt):
    slot_end_dt = datetime.combine(day, slot_end)
    if slot_end_dt <= now_dt:
        return "past"

    approved_overlapping = [
        item for item in overlapping
        if (item.status or "").upper() == ReservationStatus.APPROVED
    ]
    pending_overlapping = [
        item for item in overlapping
        if (item.status or "").upper() == ReservationStatus.PENDING
    ]

    if approved_overlapping and any(
        datetime.combine(day, item.start_time) <= now_dt < datetime.combine(day, item.end_time)
        for item in approved_overlapping
    ):
        return "in_progress"

    if pending_overlapping:
        return "pending"

    if approved_overlapping:
        return "occupied"

    return "available"


def build_week_schedule(week_days, selected_room=None, rooms_scope: list[str] | None = None):
    week_start = week_days[0]
    week_end = week_days[-1]

    valid_statuses = {ReservationStatus.APPROVED, ReservationStatus.PENDING}
    normalized_reservation_status = func.upper(func.trim(func.coalesce(Reservation.status, "")))
    q = (
        Reservation.query
        .filter(normalized_reservation_status.in_(valid_statuses))
        .filter(Reservation.date >= week_start)
        .filter(Reservation.date <= week_end)
    )

    scoped_rooms = list(rooms_scope or ROOMS)
    if selected_room:
        room_variants = lab_room_code_variants(selected_room)
        q = q.filter(Reservation.room.in_(room_variants) if room_variants else Reservation.room == selected_room)
        room_list = [selected_room]
    else:
        room_list = scoped_rooms
        if room_list:
            room_filter_values = {room for room in room_list}
            for room_value in room_list:
                room_filter_values.update(lab_room_code_variants(room_value))
            q = q.filter(Reservation.room.in_(sorted(room_filter_values)))

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
    room_lookup_by_normalized = {
        normalize_lab_room_code(room): room
        for room in room_list
    }

    for r in reservations:
        normalized_room = normalize_lab_room_code(r.room)
        room_key = room_lookup_by_normalized.get(normalized_room)
        if room_key and r.date in schedule[room_key]:
            schedule[room_key][r.date]["items"].append(r)

    now_dt = datetime.now()
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

                state = _compute_slot_state(
                    day=day,
                    slot_end=slot_end,
                    overlapping=overlapping,
                    now_dt=now_dt,
                )

                slot_rows.append({
                    "start": start_label,
                    "end": end_label,
                    "start_label": _format_ampm(slot_start),
                    "end_label": _format_ampm(slot_end),
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
    expire_unapproved_reservations()

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

    signature_url_map = {r.id: _signature_asset_url(getattr(r, "signature_ref", None)) for r in reservations}

    return render_template(
        "reservations/my_reservations.html",
        reservations=reservations,
        signature_url_map=signature_url_map,
        active_page="reservations"
    )


@reservations_bp.route("/my/<int:reservation_id>/ticket", methods=["GET", "POST"])
@min_role_required("STUDENT")
def my_active_ticket(reservation_id: int):
    reservation = Reservation.query.filter(
        Reservation.id == reservation_id,
        Reservation.user_id == current_user.id,
    ).first()
    if not reservation:
        flash("Reserva no encontrada.", "error")
        return redirect(url_for("reservations.my_reservations"))

    flash("La gestión de materiales ahora se realiza desde Solicitud de material.", "info")
    return redirect(url_for("inventory_requests.my_daily_request"))


@reservations_bp.route("/my/tickets/<int:ticket_id>/request-close", methods=["POST"])
@min_role_required("STUDENT")
def my_ticket_request_close(ticket_id: int):
    ticket = LabTicket.query.filter(
        LabTicket.id == ticket_id,
        LabTicket.owner_user_id == current_user.id,
    ).first()
    if not ticket:
        flash("Reserva no encontrada.", "error")
        return redirect(url_for("reservations.my_reservations"))

    flash("La solicitud de materiales se atiende desde el módulo Solicitud de material.", "info")
    return redirect(url_for("inventory_requests.my_daily_request"))


@reservations_bp.route("/request", methods=["GET", "POST"])
@min_role_required("STUDENT")
def request_reservation():
    expire_unapproved_reservations()

    if user_has_open_debts(current_user.id):
        flash("Tienes un adeudo activo. No puedes solicitar reservas.", "error")
        return redirect(url_for("reservations.my_reservations"))
    if is_admin_role(current_user.role):
        return redirect(url_for("reservations.admin_queue"))

    week_start_s = (request.args.get("week_start") or "").strip()
    calendar_room = (request.args.get("calendar_room") or "").strip()
    calendar_building = (request.args.get("calendar_building") or "").strip().upper()

    try:
        base_date = parse_date(week_start_s) if week_start_s else datetime.today().date()
    except ValueError:
        base_date = datetime.today().date()

    week_start = get_week_start(base_date)
    week_days = build_week_days(week_start)
    week_end = week_days[-1]

    calendar_buildings = sorted({room[:1] for room in ROOMS})
    calendar_rooms_by_building = {building: _rooms_by_building(building) for building in calendar_buildings}
    selected_calendar_building = calendar_building if calendar_building in calendar_buildings else ""
    available_calendar_rooms = _rooms_by_building(selected_calendar_building)
    selected_calendar_room = calendar_room if calendar_room in available_calendar_rooms else ""
    week_schedule, calendar_rooms = build_week_schedule(
        week_days=week_days,
        selected_room=selected_calendar_room or None,
        rooms_scope=available_calendar_rooms,
    )
    calendar_day_s = (request.args.get("calendar_day") or "").strip()
    day_filter_active = False
    try:
        selected_calendar_day = parse_date(calendar_day_s) if calendar_day_s else base_date
        day_filter_active = bool(calendar_day_s)
    except ValueError:
        selected_calendar_day = base_date
    if selected_calendar_day not in week_days:
        selected_calendar_day = week_start
        day_filter_active = False

    daily_schedule = []
    for room in calendar_rooms:
        day_cell = week_schedule.get(room, {}).get(selected_calendar_day, {})
        slots = day_cell.get("slots", []) if isinstance(day_cell, dict) else []
        items = day_cell.get("items", []) if isinstance(day_cell, dict) else []
        cell_state = "available"
        if slots:
            slot_states = [slot.get("state") for slot in slots]
            if "pending" in slot_states:
                cell_state = "pending"
            elif "in_progress" in slot_states:
                cell_state = "progress"
            elif "occupied" in slot_states:
                cell_state = "occupied"
        daily_schedule.append(
            {
                "room": room,
                "slots": slots,
                "items": items,
                "state": cell_state,
            }
        )

    prev_week = week_start - timedelta(days=7)
    next_week = week_start + timedelta(days=7)

    is_professor = _is_professor_role(current_user.role)
    assignments = _professor_assignments(current_user.id) if is_professor else []
    professor_subjects = sorted({_assignment_subject_name(a) for a in assignments if _assignment_subject_name(a)})
    professor_groups_by_subject = {}
    for assignment in assignments:
        subject_name = _assignment_subject_name(assignment)
        if not subject_name:
            continue
        professor_groups_by_subject.setdefault(subject_name, set()).add((assignment.group_code or "").strip().upper())
    professor_groups_by_subject = {
        subject_name: sorted(groups)
        for subject_name, groups in professor_groups_by_subject.items()
    }
    if request.method == "POST":
        legacy_material_fields = {"request_materials", "material_id[]", "quantity[]"}
        if any(field in request.form for field in legacy_material_fields):
            logger.info(
                "Ignoring legacy material fields in reservation request submit",
                extra={"user_id": current_user.id, "legacy_fields": sorted(legacy_material_fields)},
            )

        room = (request.form.get("room") or "").strip()
        date_s = (request.form.get("date") or "").strip()
        start_s = (request.form.get("start_time") or "").strip()
        end_s = (request.form.get("end_time") or "").strip()
        purpose = (request.form.get("purpose") or "").strip()
        group_name = (request.form.get("group_name") or "").strip()
        requester_name = _build_requester_name()
        subject = (request.form.get("subject") or "").strip().upper()
        signature_data = request.form.get("signature_data") or ""
        selected_subject_id = None

        group_name, group_error = normalize_and_validate_group_code(group_name)
        if group_name:
            group_name = group_name.upper()
        if group_error:
            flash(group_error, "error")
            return redirect(url_for("reservations.request_reservation"))

        if is_professor:
            if not assignments:
                flash("No tienes materias asignadas. Completa tu perfil o solicita actualización de materias.", "error")
                return redirect(url_for("reservations.request_reservation"))

            valid_assignment = next(
                (
                    a for a in assignments
                    if _assignment_subject_name(a).lower() == subject.lower() and a.group_code == group_name
                ),
                None,
            )
            if not valid_assignment:
                flash("La materia/grupo seleccionados no pertenecen a tu carga académica.", "error")
                return redirect(url_for("reservations.request_reservation"))
            subject = _assignment_subject_name(valid_assignment).upper()
            selected_subject_id = valid_assignment.subject_id

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
            matched_subject = Subject.query.filter(func.upper(Subject.name) == subject.upper()).first()
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

        today = datetime.today().date()
        if date_ < today:
            flash("No puedes reservar en fechas pasadas.", "error")
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

        admin_notifications = notify_roles(
            roles=["ADMIN", "SUPERADMIN", "STAFF"],
            title="Nueva reservación recibida",
            message=build_reservation_message(
                "created",
                actor_name=(current_user.full_name or current_user.email),
                room=room,
                time_range=f"{start_t.strftime('%H:%M')} - {end_t.strftime('%H:%M')}",
            ),
            link=url_for("reservations.admin_queue"),
            entity_name=f"Reserva #{r.id} · {room}",
            time_range=f"{start_t.strftime('%H:%M')} - {end_t.strftime('%H:%M')}",
            extra_context=f"Fecha {date_}",
            priority="low",
        )

        log_event(
            module="RESERVATIONS",
            action="RESERVATION_CREATED",
            user_id=current_user.id,
            entity_label=f"Reservation #{r.id}",
            description=f"Reserva creada para {room} {date_} {start_t}-{end_t}",
            metadata={"reservation_id": r.id, "room": room, "status": ReservationStatus.PENDING},
        )

        db.session.commit()
        publish_notifications_safe(
            admin_notifications,
            logger=logger,
            event_label="reservation request",
            extra={"reservation_id": r.id},
        )

        flash("Solicitud enviada. Queda pendiente de aprobación.", "success")
        return redirect(url_for("reservations.my_reservations"))

    base_context = dict(
        calendar_buildings=calendar_buildings,
        calendar_rooms_by_building=calendar_rooms_by_building,
        calendar_filter_rooms=available_calendar_rooms,
        week_days=week_days,
        week_start=week_start,
        week_end=week_end,
        week_schedule=week_schedule,
        calendar_rooms=calendar_rooms,
        selected_calendar_building=selected_calendar_building,
        selected_calendar_room=selected_calendar_room,
        selected_calendar_day=selected_calendar_day,
        day_filter_active=day_filter_active,
        daily_schedule=daily_schedule,
        today=datetime.today().date(),
        calendar_now=datetime.now(),
        prev_week=prev_week,
        next_week=next_week,
        student_group_name=(current_user.group_name or "").strip() if _is_student_role(current_user.role) else "",
    )

    if request.args.get("calendar_partial") == "1" or request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return render_template("reservations/_weekly_calendar_content.html", **base_context)

    return render_template(
        "reservations/request.html",
        rooms=ROOMS,
        is_professor=is_professor,
        professor_subjects=professor_subjects,
        professor_groups_by_subject=professor_groups_by_subject,
        active_page="reservations",
        **base_context,
    )

@reservations_bp.route("/admin", methods=["GET"])
@min_role_required("ADMIN")
def admin_queue():
    expire_unapproved_reservations()

    week_start_s = (request.args.get("week_start") or "").strip()
    calendar_room = (request.args.get("calendar_room") or "").strip()
    calendar_building = (request.args.get("calendar_building") or "").strip().upper()

    try:
        base_date = parse_date(week_start_s) if week_start_s else datetime.today().date()
    except ValueError:
        base_date = datetime.today().date()

    week_start = get_week_start(base_date)
    week_days = build_week_days(week_start)
    week_end = week_days[-1]
    prev_week = week_start - timedelta(days=7)
    next_week = week_start + timedelta(days=7)

    calendar_buildings = sorted({room[:1] for room in ROOMS})
    selected_calendar_building = calendar_building if calendar_building in calendar_buildings else ""
    available_calendar_rooms = _rooms_by_building(selected_calendar_building)
    selected_calendar_room = calendar_room if calendar_room in available_calendar_rooms else ""
    week_schedule, calendar_rooms = build_week_schedule(
        week_days=week_days,
        selected_room=selected_calendar_room or None,
        rooms_scope=available_calendar_rooms,
    )

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
    signature_url_map = {r.id: _signature_asset_url(getattr(r, "signature_ref", None)) for r in pending}
    base_context = dict(
        reservations=pending,
        signature_url_map=signature_url_map,
        week_days=week_days,
        week_start=week_start,
        week_end=week_end,
        prev_week=prev_week,
        next_week=next_week,
        week_schedule=week_schedule,
        calendar_rooms=calendar_rooms,
        calendar_buildings=calendar_buildings,
        calendar_filter_rooms=available_calendar_rooms,
        selected_calendar_building=selected_calendar_building,
        selected_calendar_room=selected_calendar_room,
        calendar_now=datetime.now(),
        active_page="reservations"
    )

    if request.args.get("calendar_partial") == "1" or request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return render_template("reservations/_admin_weekly_calendar_content.html", **base_context)

    return render_template(
        "reservations/admin_queue.html",
        **base_context,
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
            r.operation_state = "EN_PROGRESO"
            continue

        open_window_start = (datetime.combine(r.date, r.start_time) - timedelta(minutes=30)).time()
        open_window_end = r.end_time

        if current_time < open_window_start:
            r.can_open_ticket = False
            r.open_ticket_reason = "too_early"
            r.operation_state = "EN_PROGRESO"
        elif current_time > open_window_end:
            r.can_open_ticket = False
            r.open_ticket_reason = "expired"
            r.operation_state = "FINALIZADO"
        else:
            r.can_open_ticket = True
            r.open_ticket_reason = "available"
            r.operation_state = "EN_PROGRESO"

    return render_template(
        "reservations/admin_approved.html",
        reservations=approved,
        active_page="reservations"
    )


@reservations_bp.route("/admin/tickets/closure-requests", methods=["GET"])
@min_role_required("ADMIN")
def admin_ticket_closure_requests():
    flash("La operación de materiales se centralizó en Solicitudes de material.", "info")
    return redirect(url_for("inventory_requests.admin_daily_requests"))

@reservations_bp.route("/admin/approved/history", methods=["GET"])
@min_role_required("ADMIN")
def admin_approved_history():
    today = datetime.now().date()
    user_filter = (request.args.get("user") or "").strip()
    requester_filter = (request.args.get("requester") or "").strip()

    query = (
        Reservation.query
        .options(
            joinedload(Reservation.items).joinedload(ReservationItem.material),
            joinedload(Reservation.lab_tickets),
            joinedload(Reservation.user)
        )
        .outerjoin(User, Reservation.user_id == User.id)
        .filter(Reservation.status == ReservationStatus.APPROVED)
        .filter(Reservation.date < today)
    )
    if user_filter:
        like_user = f"%{user_filter}%"
        query = query.filter(
            db.or_(
                User.email.ilike(like_user),
                db.func.coalesce(User.full_name, "").ilike(like_user),
            )
        )
    if requester_filter:
        query = query.filter(db.func.coalesce(Reservation.teacher_name, "").ilike(f"%{requester_filter}%"))
    reservations = query.order_by(Reservation.date.desc(), Reservation.start_time.desc()).all()

    return render_template(
        "reservations/admin_approved_history.html",
        reservations=reservations,
        user_filter=user_filter,
        requester_filter=requester_filter,
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
    publish_notifications_safe(
        [approval_notification],
        logger=logger,
        event_label="reservation approval",
        extra={"reservation_id": r.id},
    )

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
    publish_notifications_safe(
        [rejection_notification],
        logger=logger,
        event_label="reservation rejection",
        extra={"reservation_id": r.id},
    )

    flash("Reserva rechazada.", "success")
    return redirect(url_for("reservations.admin_queue"))


@reservations_bp.route("/admin/<int:res_id>/open-ticket", methods=["POST"])
@min_role_required("ADMIN")
def admin_open_ticket(res_id: int):
    flash("En esta fase demo, las reservaciones no abren tickets. Usa Solicitudes de material.", "info")
    return redirect(url_for("reservations.admin_approved"))

@reservations_bp.route("/admin/tickets/<int:ticket_id>", methods=["GET"])
@min_role_required("ADMIN")
def admin_ticket_detail(ticket_id: int):
    flash("La operación de materiales ahora se gestiona en Solicitudes de material.", "info")
    return redirect(url_for("inventory_requests.admin_daily_requests"))


@reservations_bp.route("/admin/tickets/items/<int:item_id>/update", methods=["POST"])
@min_role_required("ADMIN")
def admin_ticket_item_update(item_id: int):
    _ = item_id
    flash("La operación de materiales ahora se gestiona en Solicitudes de material.", "info")
    return redirect(url_for("inventory_requests.admin_daily_requests"))


@reservations_bp.route("/admin/tickets/items/<int:item_id>/ready", methods=["POST"])
@min_role_required("ADMIN")
def admin_ticket_item_mark_ready(item_id: int):
    _ = item_id
    flash("La operación de materiales ahora se gestiona en Solicitudes de material.", "info")
    return redirect(url_for("inventory_requests.admin_daily_requests"))


@reservations_bp.route("/admin/tickets/<int:ticket_id>/close", methods=["POST"])
@min_role_required("ADMIN")
def admin_ticket_close(ticket_id: int):
    _ = ticket_id
    flash("La operación de materiales ahora se gestiona en Solicitudes de material.", "info")
    return redirect(url_for("inventory_requests.admin_daily_requests"))

@reservations_bp.route("/admin/tickets/<int:ticket_id>/update-all", methods=["POST"])
@min_role_required("ADMIN")
def admin_ticket_update_all(ticket_id: int):
    _ = ticket_id
    flash("La operación de materiales ahora se gestiona en Solicitudes de material.", "info")
    return redirect(url_for("inventory_requests.admin_daily_requests"))
