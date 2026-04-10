from datetime import datetime
import json

from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for
from flask_login import current_user
from sqlalchemy import func
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.models.inventory_request_item import InventoryRequestItem
from app.models.inventory_request_ticket import InventoryRequestTicket
from app.models.debt import Debt
from app.models.material import Material
from app.models.notification import Notification
from app.services.audit_service import log_event
from app.services.notification_service import build_notification, notify_roles, publish_notifications_safe
from app.utils.authz import min_role_required
from app.utils.roles import ROLE_STUDENT, is_admin_role, normalize_role
from app.utils.statuses import DebtStatus, InventoryRequestStatus


inventory_requests_bp = Blueprint("inventory_requests", __name__, url_prefix="/inventory-requests")


STATUS_OPEN = InventoryRequestStatus.OPEN
STATUS_READY = InventoryRequestStatus.READY
STATUS_CLOSED = InventoryRequestStatus.CLOSED
DEBT_CLOSED_MARKER = "[CERRADO_CON_ADEUDO]"
RETURN_REGISTERED_MARKER = "[DEVOLUCION_REGISTRADA]"
REJECTED_MARKER = "[RECHAZADA]"
PARTIAL_DELIVERY_NOTE_MARKER = "[NOTA_ENTREGA_PARCIAL]"
CLOSURE_ADMIN_PREFIX = "[Cierre admin]"


def _extract_ticket_base_reason(notes: str | None) -> str:
    if not notes:
        return ""
    for line in [line.strip() for line in notes.splitlines()]:
        if line and not line.startswith("["):
            return line
    return ""


def _extract_ticket_marker_text(notes: str | None, marker: str) -> str:
    if not notes:
        return ""
    for raw_line in notes.splitlines():
        line = raw_line.strip()
        if line.startswith(marker):
            return line[len(marker):].strip(" :-")
    return ""


def _extract_ticket_prefixed_text(notes: str | None, prefix: str) -> str:
    if not notes:
        return ""
    for raw_line in notes.splitlines():
        line = raw_line.strip()
        if line.startswith(prefix):
            return line[len(prefix):].strip(" :-")
    return ""


def _build_user_ticket_meta(ticket: InventoryRequestTicket) -> dict[str, str | bool]:
    notes = ticket.notes or ""
    rejected_reason = _extract_ticket_marker_text(notes, REJECTED_MARKER)
    partial_delivery_note = _extract_ticket_marker_text(notes, PARTIAL_DELIVERY_NOTE_MARKER)
    close_note = _extract_ticket_prefixed_text(notes, CLOSURE_ADMIN_PREFIX)
    closed_with_debt = ticket.status == STATUS_CLOSED and DEBT_CLOSED_MARKER in notes
    rejected = ticket.status == STATUS_CLOSED and bool(rejected_reason or REJECTED_MARKER in notes)
    status_label = "Abierta"
    if ticket.status == STATUS_READY:
        status_label = "Lista para recoger"
    elif ticket.status == STATUS_CLOSED:
        status_label = "Cerrada"
    if closed_with_debt:
        status_label = "Cerrado con adeudo"
    if rejected:
        status_label = "Rechazada"
    return {
        "base_reason": _extract_ticket_base_reason(notes) or "-",
        "rejected_reason": rejected_reason,
        "partial_delivery_note": partial_delivery_note,
        "close_note": close_note,
        "status_label": status_label,
        "rejected": rejected,
        "closed_with_debt": closed_with_debt,
    }


def _is_student_role(role: str | None) -> bool:
    return normalize_role(role) == ROLE_STUDENT


def _notify_admins_for_ticket(ticket: InventoryRequestTicket, message: str) -> list[Notification]:
    return notify_roles(
        roles=["ADMIN", "SUPERADMIN", "STAFF"],
        title="Nueva solicitud de material",
        message=message,
        link=url_for("inventory_requests.admin_ticket_detail", ticket_id=ticket.id),
        entity_name=f"Solicitud #{ticket.id}",
        priority="low",
    )


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


def _process_close_after_return(ticket: InventoryRequestTicket, cancel_reason: str) -> list[Debt]:
    has_missing = False
    created_debts: list[Debt] = []
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
            original_amount=missing,
            remaining_amount=missing,
        )
        db.session.add(debt)
        created_debts.append(debt)

    ticket.status = STATUS_CLOSED
    ticket.closed_at = datetime.now()
    previous_notes = (ticket.notes or "").strip()
    status_note = DEBT_CLOSED_MARKER if has_missing else "[CERRADO]"
    close_note = f"[Cierre admin] {cancel_reason}"
    ticket.notes = (
        f"{previous_notes}\n{RETURN_REGISTERED_MARKER}\n{status_note}\n{close_note}".strip()
        if previous_notes
        else f"{RETURN_REGISTERED_MARKER}\n{status_note}\n{close_note}"
    )
    log_event(
        module="INVENTORY_REQUESTS",
        action="INVENTORY_DAILY_REQUEST_CLOSED",
        user_id=current_user.id,
        entity_label=f"InventoryRequestTicket #{ticket.id}",
        description=f"Solicitud de material #{ticket.id} cerrada",
        metadata={"ticket_id": ticket.id, "target_user_id": ticket.user_id},
    )
    return created_debts


def _build_debt_created_notification(debt: Debt) -> Notification:
    material_name = debt.material.name if debt.material else "material"
    pending_amount = int(debt.remaining_amount or debt.amount or 0)
    reason = (debt.reason or "").strip()
    reason_text = f" Motivo: {reason}." if reason else ""
    return Notification(
        user_id=debt.user_id,
        title="Se generó un adeudo",
        message=(
            f"Tienes un adeudo por faltante de material: {material_name} "
            f"({pending_amount} pendiente).{reason_text}"
        ),
        link=url_for("debts.my_debts"),
    )


@inventory_requests_bp.route("/", methods=["GET"], endpoint="my_daily_request")
@min_role_required("STUDENT")
def my_daily_request():
    if is_admin_role(current_user.role):
        return redirect(url_for("inventory_requests.admin_daily_requests"))

    clear_cart_on_load = request.args.get("saved") == "1"
    if clear_cart_on_load:
        session.pop("daily_request_reason_draft", None)

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
    history_meta = {ticket.id: _build_user_ticket_meta(ticket) for ticket in history}
    active_ticket_meta = _build_user_ticket_meta(active_ticket) if active_ticket else None

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
        today_ticket_meta=active_ticket_meta,
        history=history,
        history_meta=history_meta,
        materials=materials,
        materials_json=materials_json,
        reason_draft=session.pop("daily_request_reason_draft", "") if not clear_cart_on_load else "",
        clear_cart_on_load=clear_cart_on_load,
        active_page="inventory_requests",
    )


@inventory_requests_bp.route("/add", methods=["POST"], endpoint="add_to_daily_request")
@min_role_required("STUDENT")
def add_to_daily_request():
    material_ids = request.form.getlist("material_id[]")
    quantities = request.form.getlist("quantity[]")
    request_reason = (request.form.get("request_reason") or "").strip()
    session["daily_request_reason_draft"] = request_reason

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
        f"{(current_user.full_name or current_user.email)} creó una solicitud de material.",
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
    publish_notifications_safe(
        admin_notifications,
        logger=current_app.logger,
        event_label="inventory request creation",
        extra={"ticket_id": ticket.id},
    )

    session.pop("daily_request_reason_draft", None)
    flash(f"Solicitud de material creada (#{ticket.id}).", "success")

    return redirect(url_for("inventory_requests.my_daily_request", saved="1"))


@inventory_requests_bp.route("/<int:ticket_id>", methods=["GET"], endpoint="my_ticket_detail")
@min_role_required("STUDENT")
def my_ticket_detail(ticket_id: int):
    ticket = (
        InventoryRequestTicket.query
        .options(joinedload(InventoryRequestTicket.items).joinedload(InventoryRequestItem.material))
        .filter(InventoryRequestTicket.id == ticket_id, InventoryRequestTicket.user_id == current_user.id)
        .first()
    )
    if not ticket:
        flash("Solicitud no encontrada.", "error")
        return redirect(url_for("inventory_requests.my_daily_request"))

    related_debts = (
        Debt.query
        .options(joinedload(Debt.material))
        .filter(
            Debt.user_id == current_user.id,
            Debt.reason.ilike(f"%Solicitud #{ticket.id}%"),
        )
        .order_by(Debt.created_at.desc())
        .all()
    )

    return render_template(
        "inventory_requests/my_request_detail.html",
        ticket=ticket,
        ticket_meta=_build_user_ticket_meta(ticket),
        related_debts=related_debts,
        active_page="inventory_requests",
    )


@inventory_requests_bp.route("/admin", methods=["GET"], endpoint="admin_daily_requests")
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


@inventory_requests_bp.route("/admin/<int:ticket_id>", methods=["GET"], endpoint="admin_ticket_detail")
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
        ticket_base_reason=_extract_ticket_base_reason(ticket.notes),
        rejected_reason=_extract_ticket_marker_text(ticket.notes, REJECTED_MARKER),
        partial_delivery_note=_extract_ticket_marker_text(ticket.notes, PARTIAL_DELIVERY_NOTE_MARKER),
        active_page="inventory_requests",
    )


@inventory_requests_bp.route("/admin/<int:ticket_id>/ready", methods=["POST"], endpoint="admin_mark_ready")
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

    has_partial_delivery = False

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

        if delivered < item.quantity_requested:
            has_partial_delivery = True
        item.quantity_delivered = delivered

    partial_delivery_note = (request.form.get("partial_delivery_note") or "").strip()
    if has_partial_delivery and not partial_delivery_note:
        flash("Debes registrar una nota administrativa cuando entregas menos material del solicitado.", "error")
        return redirect(url_for("inventory_requests.admin_ticket_detail", ticket_id=ticket.id))

    ok, stock_error = _apply_stock_delivery_for_request(ticket)
    if not ok:
        db.session.rollback()
        flash(stock_error or "No se pudo preparar la solicitud por stock.", "error")
        return redirect(url_for("inventory_requests.admin_ticket_detail", ticket_id=ticket.id))

    ticket.status = STATUS_READY
    ticket.ready_at = datetime.now()
    if has_partial_delivery:
        previous_notes = (ticket.notes or "").strip()
        partial_note_line = f"{PARTIAL_DELIVERY_NOTE_MARKER} {partial_delivery_note}"
        ticket.notes = (
            f"{previous_notes}\n{partial_note_line}".strip()
            if previous_notes
            else partial_note_line
        )

    notification = Notification(
        user_id=ticket.user_id,
        title="Solicitud de material lista para recoger",
        message="Tu solicitud de material está lista para recoger.",
        link=url_for("inventory_requests.my_ticket_detail", ticket_id=ticket.id),
    )
    setattr(notification, "_priority", "medium")
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
    publish_notifications_safe(
        [notification],
        logger=current_app.logger,
        event_label="inventory request ready",
        extra={"ticket_id": ticket.id},
    )

    flash("Solicitud marcada como lista y usuario notificado.", "success")
    return redirect(url_for("inventory_requests.admin_ticket_detail", ticket_id=ticket.id))


@inventory_requests_bp.route("/admin/<int:ticket_id>/reject", methods=["POST"], endpoint="admin_reject_ticket")
@min_role_required("ADMIN")
def admin_reject_ticket(ticket_id: int):
    ticket = InventoryRequestTicket.query.get(ticket_id)
    if not ticket:
        flash("Solicitud no encontrada.", "error")
        return redirect(url_for("inventory_requests.admin_daily_requests"))
    if ticket.status != STATUS_OPEN:
        flash("Solo puedes rechazar solicitudes abiertas.", "error")
        return redirect(url_for("inventory_requests.admin_ticket_detail", ticket_id=ticket.id))

    reject_reason = (request.form.get("reject_reason") or "").strip()
    if not reject_reason:
        flash("Debes capturar un motivo de rechazo.", "error")
        return redirect(url_for("inventory_requests.admin_ticket_detail", ticket_id=ticket.id))

    base_reason = _extract_ticket_base_reason(ticket.notes)
    rejection_line = f"{REJECTED_MARKER} {reject_reason}"
    ticket.notes = f"{base_reason}\n{rejection_line}".strip() if base_reason else rejection_line
    ticket.status = STATUS_CLOSED
    ticket.closed_at = datetime.now()

    notification = Notification(
        user_id=ticket.user_id,
        title="Solicitud de material rechazada",
        message=f"Tu solicitud de material fue rechazada. Motivo: {reject_reason}",
        link=url_for("inventory_requests.my_ticket_detail", ticket_id=ticket.id),
    )
    setattr(notification, "_priority", "high")
    db.session.add(notification)
    log_event(
        module="INVENTORY_REQUESTS",
        action="INVENTORY_DAILY_REQUEST_REJECTED",
        user_id=current_user.id,
        entity_label=f"InventoryRequestTicket #{ticket.id}",
        description=f"Solicitud de material #{ticket.id} rechazada",
        metadata={"ticket_id": ticket.id, "target_user_id": ticket.user_id},
    )

    db.session.commit()
    publish_notifications_safe(
        [notification],
        logger=current_app.logger,
        event_label="inventory request rejection",
        extra={"ticket_id": ticket.id},
    )
    flash("Solicitud rechazada correctamente.", "success")
    return redirect(url_for("inventory_requests.admin_ticket_detail", ticket_id=ticket.id))


@inventory_requests_bp.route("/admin/<int:ticket_id>/return", methods=["POST"], endpoint="admin_register_return")
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

    cancel_reason = (request.form.get("cancel_reason") or "").strip()
    if not cancel_reason:
        flash("Debes capturar el motivo para cerrar/cancelar la solicitud.", "error")
        return redirect(url_for("inventory_requests.admin_ticket_detail", ticket_id=ticket.id))

    created_debts = _process_close_after_return(ticket=ticket, cancel_reason=cancel_reason)

    requester_notifications: list[Notification] = [
        build_notification(
            user_id=ticket.user_id,
            title="Tu solicitud de material fue cerrada",
            message="La solicitud fue cerrada tras registrar devolución.",
            link=url_for("inventory_requests.my_ticket_detail", ticket_id=ticket.id),
            entity_name=f"Solicitud #{ticket.id}",
            extra_context=f"Motivo: {cancel_reason}",
            priority="medium",
        )
    ]
    if created_debts:
        requester_notifications.extend(_build_debt_created_notification(debt) for debt in created_debts)

    admin_notifications = notify_roles(
        roles=["ADMIN", "SUPERADMIN", "STAFF"],
        title="Solicitud de material cerrada",
        message=f"La solicitud fue cerrada. {'Se generaron adeudos.' if created_debts else 'Sin adeudos.'}",
        link=url_for("inventory_requests.admin_ticket_detail", ticket_id=ticket.id),
        entity_name=f"Solicitud #{ticket.id}",
        actor_name=(current_user.full_name or current_user.email),
        priority="high" if created_debts else "medium",
    )

    db.session.commit()
    publish_notifications_safe(
        [*requester_notifications, *admin_notifications],
        logger=current_app.logger,
        event_label="inventory request return closure",
        extra={"ticket_id": ticket.id, "created_debts": len(created_debts)},
    )
    flash("Devolución guardada y solicitud cerrada.", "success")
    return redirect(url_for("inventory_requests.admin_ticket_detail", ticket_id=ticket.id))
