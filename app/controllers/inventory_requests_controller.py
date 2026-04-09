from datetime import datetime
import json

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy import func
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.models.inventory_request_item import InventoryRequestItem
from app.models.inventory_request_ticket import InventoryRequestTicket
from app.models.material import Material
from app.models.notification import Notification
from app.models.user import User
from app.services.audit_service import log_event
from app.services.notification_realtime_service import publish_notification_created
from app.utils.authz import min_role_required
from app.utils.roles import ROLE_STUDENT, normalize_role
from app.utils.statuses import InventoryRequestStatus


inventory_requests_bp = Blueprint("inventory_requests", __name__, url_prefix="/inventory-requests")


STATUS_OPEN = InventoryRequestStatus.OPEN
STATUS_READY = InventoryRequestStatus.READY_FOR_PICKUP
STATUS_CLOSED = InventoryRequestStatus.CLOSED


def _is_student_role(role: str | None) -> bool:
    return normalize_role(role) == ROLE_STUDENT


def _notify_admins_for_ticket(ticket: InventoryRequestTicket, message: str) -> list[Notification]:
    admins = User.query.filter(User.role.in_(["ADMIN", "SUPERADMIN"])).all()
    notifications_created: list[Notification] = []
    for admin in admins:
        notif = Notification(
            user_id=admin.id,
            title="Solicitud de material actualizada",
            message=message,
            link=url_for("inventory_requests.admin_ticket_detail", ticket_id=ticket.id),
        )
        db.session.add(notif)
        notifications_created.append(notif)
    return notifications_created


def _close_stale_open_tickets() -> None:
    # Compatibilidad temporal: el flujo dejó de ser "ticket diario".
    # Se conserva la función para no romper llamadas existentes.
    return None


@inventory_requests_bp.route("/", methods=["GET"])
@min_role_required("STUDENT")
def my_daily_request():
    active_ticket = (
        InventoryRequestTicket.query
        .options(joinedload(InventoryRequestTicket.items).joinedload(InventoryRequestItem.material))
        .filter(InventoryRequestTicket.user_id == current_user.id)
        .filter(InventoryRequestTicket.status.in_([STATUS_OPEN, STATUS_READY]))
        .order_by(InventoryRequestTicket.created_at.desc())
        .first()
    )

    history = (
        InventoryRequestTicket.query
        .filter(InventoryRequestTicket.user_id == current_user.id)
        .order_by(InventoryRequestTicket.request_date.desc(), InventoryRequestTicket.created_at.desc())
        .limit(20)
        .all()
    )

    materials = (
        Material.query
        .filter(func.lower(func.coalesce(Material.status, "")) != "baja")
        .filter(Material.career_id == current_user.career_id if _is_student_role(current_user.role) else True)
        .order_by(Material.name.asc())
        .all()
    )
    materials_json = json.dumps([
        {
            "id": m.id,
            "name": m.name,
            "pieces_qty": m.pieces_qty if m.pieces_qty is not None else 0,
        }
        for m in materials
    ])

    return render_template(
        "inventory_requests/my_daily_request.html",
        today_ticket=active_ticket,
        history=history,
        materials=materials,
        materials_json=materials_json,
        active_page="inventory_requests",
    )


@inventory_requests_bp.route("/add", methods=["POST"])
@min_role_required("STUDENT")
def add_to_daily_request():
    material_ids = request.form.getlist("material_id[]")
    quantities = request.form.getlist("quantity[]")
    request_reason = (request.form.get("request_reason") or "").strip()

    if not request_reason:
        flash("Debes indicar la materia o motivo de la solicitud.", "error")
        return redirect(url_for("inventory_requests.my_daily_request"))

    parsed_items = []
    for i in range(len(material_ids)):
        try:
            material_id = int(material_ids[i])
            qty = int(quantities[i])
        except (ValueError, IndexError):
            continue

        if qty <= 0:
            flash("Cantidad inválida: debe ser mayor a cero.", "error")
            return redirect(url_for("inventory_requests.my_daily_request"))

        material = Material.query.get(material_id)
        if not material:
            flash("Uno de los materiales seleccionados no existe.", "error")
            return redirect(url_for("inventory_requests.my_daily_request"))
        if (material.status or "").strip().lower() == "baja":
            flash(f"{material.name}: el material está en baja y no se puede solicitar.", "error")
            return redirect(url_for("inventory_requests.my_daily_request"))
        if _is_student_role(current_user.role) and material.career_id != current_user.career_id:
            flash(f"{material.name}: no pertenece a tu carrera.", "error")
            return redirect(url_for("inventory_requests.my_daily_request"))

        if material.pieces_qty is not None and qty > material.pieces_qty:
            flash(f"{material.name}: solo hay {material.pieces_qty} disponibles.", "error")
            return redirect(url_for("inventory_requests.my_daily_request"))

        parsed_items.append((material, qty))

    if not parsed_items:
        flash("Agrega al menos un material válido con cantidad positiva.", "error")
        return redirect(url_for("inventory_requests.my_daily_request"))

    ticket = InventoryRequestTicket(
        user_id=current_user.id,
        request_date=datetime.now().date(),
        status=STATUS_OPEN,
        notes=request_reason,
    )
    db.session.add(ticket)
    db.session.flush()

    for material, qty in parsed_items:
        db.session.add(
            InventoryRequestItem(
                ticket_id=ticket.id,
                material_id=material.id,
                quantity_requested=qty,
            )
        )

    admin_notifications = _notify_admins_for_ticket(
        ticket,
        f"El usuario {current_user.email} creó la solicitud de material #{ticket.id}.",
    )

    log_event(
        module="INVENTORY_REQUESTS",
        action="INVENTORY_DAILY_REQUEST_CREATED",
        user_id=current_user.id,
        entity_label=f"InventoryRequestTicket #{ticket.id}",
        description="Solicitud de material creada",
        metadata={"ticket_id": ticket.id, "request_date": str(ticket.request_date)},
    )

    db.session.commit()
    for notif in admin_notifications:
        publish_notification_created(notif)

    flash(f"Solicitud de material creada (ticket #{ticket.id}).", "success")

    return redirect(url_for("inventory_requests.my_daily_request"))


@inventory_requests_bp.route("/admin", methods=["GET"])
@min_role_required("ADMIN")
def admin_daily_requests():
    _close_stale_open_tickets()

    tickets = (
        InventoryRequestTicket.query
        .options(
            joinedload(InventoryRequestTicket.user),
            joinedload(InventoryRequestTicket.items).joinedload(InventoryRequestItem.material),
        )
        .filter(InventoryRequestTicket.status.in_([STATUS_OPEN, STATUS_READY]))
        .order_by(InventoryRequestTicket.request_date.desc(), InventoryRequestTicket.created_at.asc())
        .all()
    )

    return render_template(
        "inventory_requests/admin_list.html",
        tickets=tickets,
        active_page="inventory_requests",
    )


@inventory_requests_bp.route("/admin/<int:ticket_id>", methods=["GET"])
@min_role_required("ADMIN")
def admin_ticket_detail(ticket_id: int):
    _close_stale_open_tickets()

    ticket = (
        InventoryRequestTicket.query
        .options(
            joinedload(InventoryRequestTicket.user),
            joinedload(InventoryRequestTicket.items).joinedload(InventoryRequestItem.material),
        )
        .filter(InventoryRequestTicket.id == ticket_id)
        .first()
    )

    if not ticket:
        flash("Solicitud no encontrada.", "error")
        return redirect(url_for("inventory_requests.admin_daily_requests"))

    return render_template(
        "inventory_requests/admin_detail.html",
        ticket=ticket,
        active_page="inventory_requests",
    )


@inventory_requests_bp.route("/admin/<int:ticket_id>/ready", methods=["POST"])
@min_role_required("ADMIN")
def admin_mark_ready(ticket_id: int):
    _close_stale_open_tickets()

    ticket = InventoryRequestTicket.query.get(ticket_id)
    if not ticket:
        flash("Solicitud no encontrada.", "error")
        return redirect(url_for("inventory_requests.admin_daily_requests"))

    if ticket.status == STATUS_CLOSED:
        flash("No puedes marcar como lista una solicitud cerrada.", "error")
        return redirect(url_for("inventory_requests.admin_ticket_detail", ticket_id=ticket.id))

    ticket.status = STATUS_READY
    ticket.ready_at = datetime.now()

    notification = Notification(
        user_id=ticket.user_id,
        title="Solicitud de material lista para recoger",
        message=f"Tu solicitud de material #{ticket.id} está lista para recoger.",
        link=url_for("inventory_requests.my_daily_request"),
    )
    db.session.add(notification)
    log_event(
        module="INVENTORY_REQUESTS",
        action="INVENTORY_DAILY_REQUEST_READY",
        user_id=current_user.id,
        entity_label=f"InventoryRequestTicket #{ticket.id}",
        description=f"Solicitud de material #{ticket.id} marcada lista para recoger",
        metadata={"ticket_id": ticket.id, "target_user_id": ticket.user_id},
    )

    db.session.commit()
    publish_notification_created(notification)

    flash("Solicitud marcada como lista y usuario notificado.", "success")
    return redirect(url_for("inventory_requests.admin_ticket_detail", ticket_id=ticket.id))


@inventory_requests_bp.route("/admin/<int:ticket_id>/close", methods=["POST"])
@min_role_required("ADMIN")
def admin_close_ticket(ticket_id: int):
    _close_stale_open_tickets()

    ticket = InventoryRequestTicket.query.get(ticket_id)
    if not ticket:
        flash("Solicitud no encontrada.", "error")
        return redirect(url_for("inventory_requests.admin_daily_requests"))

    if ticket.status == STATUS_CLOSED:
        flash("La solicitud ya está cerrada.", "warning")
        return redirect(url_for("inventory_requests.admin_ticket_detail", ticket_id=ticket.id))

    cancel_reason = (request.form.get("cancel_reason") or "").strip()
    if not cancel_reason:
        flash("Debes capturar el motivo para cerrar/cancelar la solicitud.", "error")
        return redirect(url_for("inventory_requests.admin_ticket_detail", ticket_id=ticket.id))

    ticket.status = STATUS_CLOSED
    ticket.closed_at = datetime.now()
    previous_notes = (ticket.notes or "").strip()
    ticket.notes = f"{previous_notes}\n[Cierre admin] {cancel_reason}".strip() if previous_notes else f"[Cierre admin] {cancel_reason}"
    log_event(
        module="INVENTORY_REQUESTS",
        action="INVENTORY_DAILY_REQUEST_CLOSED",
        user_id=current_user.id,
        entity_label=f"InventoryRequestTicket #{ticket.id}",
        description=f"Solicitud de material #{ticket.id} cerrada",
        metadata={"ticket_id": ticket.id, "target_user_id": ticket.user_id},
    )

    db.session.commit()

    flash("Solicitud cerrada correctamente.", "success")
    return redirect(url_for("inventory_requests.admin_ticket_detail", ticket_id=ticket.id))
