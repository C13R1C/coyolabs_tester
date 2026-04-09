from datetime import datetime
import json

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy import func
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.models.inventory_request_item import InventoryRequestItem
from app.models.inventory_request_ticket import InventoryRequestTicket
from app.models.debt import Debt
from app.models.material import Material
from app.models.notification import Notification
from app.models.user import User
from app.services.audit_service import log_event
from app.services.notification_realtime_service import publish_notification_created
from app.utils.authz import min_role_required
from app.utils.roles import ROLE_STUDENT, normalize_role
from app.utils.statuses import DebtStatus, InventoryRequestStatus


inventory_requests_bp = Blueprint("inventory_requests", __name__, url_prefix="/inventory-requests")


STATUS_OPEN = InventoryRequestStatus.OPEN
STATUS_READY = InventoryRequestStatus.READY
STATUS_CLOSED = InventoryRequestStatus.CLOSED
DEBT_CLOSED_MARKER = "[CERRADO_CON_ADEUDO]"
RETURN_REGISTERED_MARKER = "[DEVOLUCION_REGISTRADA]"


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


def _apply_stock_delivery_for_request(ticket: InventoryRequestTicket) -> tuple[bool, str | None]:
    items = ticket.items or []
    if not items:
        return True, None

    for item in items:
        material = item.material
        if not material:
            return False, "Uno de los materiales de la solicitud ya no existe."
        if item.quantity_delivered < 0 or item.quantity_delivered > item.quantity_requested:
            return False, f"{material.name}: la cantidad entregada debe estar entre 0 y la solicitada."
        if material.pieces_qty is None:
            continue
        if item.quantity_delivered > material.pieces_qty:
            return False, f"{material.name}: stock insuficiente para entregar {item.quantity_delivered} unidad(es)."

    for item in items:
        material = item.material
        if material and material.pieces_qty is not None:
            material.pieces_qty -= item.quantity_delivered

    return True, None


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
                quantity_delivered=qty,
                quantity_returned=0,
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

    flash(f"Solicitud de material creada (#{ticket.id}).", "success")

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
    if ticket.status == STATUS_READY:
        flash("La solicitud ya está marcada como lista para recoger.", "warning")
        return redirect(url_for("inventory_requests.admin_ticket_detail", ticket_id=ticket.id))

    for item in (ticket.items or []):
        delivered_raw = (request.form.get(f"delivered_{item.id}") or "").strip()
        if delivered_raw == "":
            delivered = item.quantity_requested
        else:
            try:
                delivered = int(delivered_raw)
            except ValueError:
                flash("Cantidad entregada inválida.", "error")
                return redirect(url_for("inventory_requests.admin_ticket_detail", ticket_id=ticket.id))

        if delivered < 0 or delivered > item.quantity_requested:
            material_name = item.material.name if item.material else f"ID {item.material_id}"
            flash(f"{material_name}: la cantidad entregada debe estar entre 0 y {item.quantity_requested}.", "error")
            return redirect(url_for("inventory_requests.admin_ticket_detail", ticket_id=ticket.id))
        if item.quantity_returned > delivered:
            material_name = item.material.name if item.material else f"ID {item.material_id}"
            flash(f"{material_name}: la devolución no puede superar lo entregado.", "error")
            return redirect(url_for("inventory_requests.admin_ticket_detail", ticket_id=ticket.id))

        item.quantity_delivered = delivered

    ok, stock_error = _apply_stock_delivery_for_request(ticket)
    if not ok:
        db.session.rollback()
        flash(stock_error or "No se pudo preparar la solicitud por stock.", "error")
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


@inventory_requests_bp.route("/admin/<int:ticket_id>/return", methods=["POST"])
@min_role_required("ADMIN")
def admin_register_return(ticket_id: int):
    ticket = InventoryRequestTicket.query.get(ticket_id)
    if not ticket:
        flash("Solicitud no encontrada.", "error")
        return redirect(url_for("inventory_requests.admin_daily_requests"))
    if ticket.status != STATUS_READY:
        flash("Solo puedes registrar devolución en solicitudes listas para recoger.", "error")
        return redirect(url_for("inventory_requests.admin_ticket_detail", ticket_id=ticket.id))

    for item in (ticket.items or []):
        returned_raw = (request.form.get(f"returned_{item.id}") or "").strip()
        if returned_raw == "":
            flash("Debes capturar la cantidad devuelta para cada material.", "error")
            return redirect(url_for("inventory_requests.admin_ticket_detail", ticket_id=ticket.id))
        try:
            returned = int(returned_raw)
        except ValueError:
            flash("Cantidad devuelta inválida.", "error")
            return redirect(url_for("inventory_requests.admin_ticket_detail", ticket_id=ticket.id))

        if returned < 0 or returned > item.quantity_delivered:
            material_name = item.material.name if item.material else f"ID {item.material_id}"
            flash(f"{material_name}: la devolución debe estar entre 0 y {item.quantity_delivered}.", "error")
            return redirect(url_for("inventory_requests.admin_ticket_detail", ticket_id=ticket.id))

        item.quantity_returned = returned

    previous_notes = (ticket.notes or "").strip()
    marker = RETURN_REGISTERED_MARKER
    if marker not in previous_notes:
        ticket.notes = f"{previous_notes}\n{marker}".strip() if previous_notes else marker

    db.session.commit()
    flash("Devolución registrada.", "success")
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
    if ticket.status != STATUS_READY:
        flash("La solicitud debe pasar por estado LISTA antes de cerrarse.", "error")
        return redirect(url_for("inventory_requests.admin_ticket_detail", ticket_id=ticket.id))

    has_delivered_items = any((item.quantity_delivered or 0) > 0 for item in (ticket.items or []))
    if has_delivered_items and RETURN_REGISTERED_MARKER not in (ticket.notes or ""):
        flash("Debes registrar la devolución antes de cerrar la solicitud.", "error")
        return redirect(url_for("inventory_requests.admin_ticket_detail", ticket_id=ticket.id))

    cancel_reason = (request.form.get("cancel_reason") or "").strip()
    if not cancel_reason:
        flash("Debes capturar el motivo para cerrar/cancelar la solicitud.", "error")
        return redirect(url_for("inventory_requests.admin_ticket_detail", ticket_id=ticket.id))

    has_missing = False
    for item in (ticket.items or []):
        delivered = max(0, item.quantity_delivered or 0)
        returned = max(0, item.quantity_returned or 0)

        material = item.material
        if material and material.pieces_qty is not None and returned > 0:
            material.pieces_qty += returned

        missing = max(0, delivered - returned)
        if missing <= 0:
            continue
        has_missing = True
        material_name = item.material.name if item.material else f"Material ID {item.material_id}"
        existing_debt = (
            Debt.query
            .filter(
                Debt.user_id == ticket.user_id,
                Debt.material_id == item.material_id,
                Debt.status == DebtStatus.PENDING,
                Debt.reason.ilike(f"%Solicitud #{ticket.id}%"),
            )
            .first()
        )
        if existing_debt:
            continue
        debt = Debt(
            user_id=ticket.user_id,
            material_id=item.material_id,
            status=DebtStatus.PENDING,
            reason=f"Faltante en devolución (Solicitud #{ticket.id}) - {material_name}",
            amount=missing,
        )
        db.session.add(debt)

    ticket.status = STATUS_CLOSED
    ticket.closed_at = datetime.now()
    previous_notes = (ticket.notes or "").strip()
    status_note = DEBT_CLOSED_MARKER if has_missing else "[CERRADO]"
    close_note = f"[Cierre admin] {cancel_reason}"
    ticket.notes = f"{previous_notes}\n{status_note}\n{close_note}".strip() if previous_notes else f"{status_note}\n{close_note}"
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
