import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from flask import current_app, has_app_context, url_for

from app.extensions import db
from app.models.lab_ticket import LabTicket
from app.models.material import Material
from app.models.notification import Notification
from app.models.ticket_item import TicketItem
from app.models.user import User
from app.services.audit_service import log_event
from app.services.debt_service import create_debt_for_ticket
from app.controllers.inventory_controller import _is_inactive_status
from app.utils.statuses import (
    LabTicketStatus,
    TicketItemStatus,
    is_active_lab_ticket_status,
    is_lab_ticket_closure_requested,
)

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ServiceResult:
    ok: bool
    message: str | None = None
    data: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def success(cls, message: str | None = None, **data: Any) -> "ServiceResult":
        return cls(ok=True, message=message, data=data)

    @classmethod
    def failure(cls, message: str, **data: Any) -> "ServiceResult":
        return cls(ok=False, message=message, data=data)


def _log_ticket_rejected(action: str, actor_user: User | None, ticket: LabTicket | None, reason: str, metadata: dict | None = None) -> None:
    payload = {
        "result": "rejected",
        "reason": reason,
        "ticket_id": getattr(ticket, "id", None),
        "entity_id": getattr(ticket, "id", None),
        "ticket_status": getattr(ticket, "status", None),
    }
    if metadata:
        payload.update(metadata)
    log_event(
        module="LAB_TICKETS",
        action=action,
        user_id=getattr(actor_user, "id", None),
        entity_label=f"LabTicket #{getattr(ticket, 'id', 'N/A')}",
        description=reason,
        metadata=payload,
    )


def validate_ticket_active(ticket: LabTicket | None) -> ServiceResult:
    if not ticket:
        return ServiceResult.failure("Ticket no encontrado.")
    if ticket.status == LabTicketStatus.CLOSURE_REQUESTED:
        return ServiceResult.failure("El ticket ya tiene solicitud de cierre.")
    if ticket.status == LabTicketStatus.CLOSED:
        return ServiceResult.failure("El ticket ya está cerrado.")
    if ticket.status == LabTicketStatus.CLOSED_WITH_DEBT:
        return ServiceResult.failure("El ticket ya está cerrado con adeudo.")
    if not is_active_lab_ticket_status(ticket.status):
        return ServiceResult.failure(f"El ticket no se puede operar desde estado {ticket.status}.", ticket=ticket)
    return ServiceResult.success(ticket=ticket)


def sync_ticket_ready_status(ticket: LabTicket) -> None:
    has_pending_delivery = any(item.quantity_requested > item.quantity_delivered for item in ticket.items)
    if not has_pending_delivery and ticket.status == LabTicketStatus.READY_FOR_PICKUP:
        ticket.status = LabTicketStatus.OPEN
    return None


def apply_ticket_item_status(item: TicketItem, delivered: int, returned: int) -> None:
    if delivered == 0:
        item.status = TicketItemStatus.PENDING
    elif returned == 0:
        item.status = TicketItemStatus.DELIVERED
    else:
        item.status = TicketItemStatus.RETURNED
    return None


def add_material_to_ticket(ticket: LabTicket, material: Material, quantity: int, actor_user: User) -> ServiceResult:
    active_result = validate_ticket_active(ticket)
    if not active_result.ok:
        _log_ticket_rejected(
            action="LAB_TICKET_ITEM_REQUEST_REJECTED",
            actor_user=actor_user,
            ticket=ticket,
            reason=active_result.message or "Ticket inactivo.",
            metadata={"material_id": getattr(material, "id", None), "quantity_attempted": quantity},
        )
        return active_result

    if quantity <= 0:
        message = "Selecciona material y una cantidad válida."
        _log_ticket_rejected(
            action="LAB_TICKET_ITEM_REQUEST_REJECTED",
            actor_user=actor_user,
            ticket=ticket,
            reason=message,
            metadata={"material_id": getattr(material, "id", None), "quantity_attempted": quantity},
        )
        return ServiceResult.failure(message)

    if _is_inactive_status(material.status):
        message = f"{material.name}: está inactivo y no se puede solicitar."
        _log_ticket_rejected(
            action="LAB_TICKET_ITEM_REQUEST_REJECTED",
            actor_user=actor_user,
            ticket=ticket,
            reason=message,
            metadata={"material_id": material.id, "quantity_attempted": quantity, "material_status": material.status},
        )
        return ServiceResult.failure(message)

    if material.pieces_qty is not None and quantity > material.pieces_qty:
        message = f"{material.name}: solo hay {material.pieces_qty} disponibles para solicitud."
        _log_ticket_rejected(
            action="LAB_TICKET_ITEM_REQUEST_REJECTED",
            actor_user=actor_user,
            ticket=ticket,
            reason=message,
            metadata={"material_id": material.id, "quantity_attempted": quantity},
        )
        return ServiceResult.failure(message)

    item = TicketItem.query.filter_by(ticket_id=ticket.id, material_id=material.id).first()
    if item:
        item.quantity_requested += quantity
        if item.quantity_delivered < item.quantity_requested:
            item.status = TicketItemStatus.REQUESTED
    else:
        item = TicketItem(
            ticket_id=ticket.id,
            material_id=material.id,
            quantity_requested=quantity,
            quantity_delivered=0,
            quantity_returned=0,
            status=TicketItemStatus.REQUESTED,
        )
        db.session.add(item)

    sync_ticket_ready_status(ticket)

    admins = User.query.filter(User.role.in_(["ADMIN", "SUPERADMIN"])).all()
    notifications: list[Notification] = []
    for admin in admins:
        notif = Notification(
            user_id=admin.id,
            title="Solicitud urgente en ticket activo",
            message=f"{actor_user.email} agregó {quantity} de {material.name} al ticket #{ticket.id}.",
            link=url_for("reservations.admin_ticket_detail", ticket_id=ticket.id),
        )
        db.session.add(notif)
        notifications.append(notif)

    log_event(
        module="LAB_TICKETS",
        action="LAB_TICKET_ITEM_REQUESTED_BY_USER",
        user_id=actor_user.id,
        entity_label=f"LabTicket #{ticket.id}",
        description=f"Usuario agregó material al ticket activo #{ticket.id}",
        metadata={"ticket_id": ticket.id, "material_id": material.id, "quantity_added": quantity},
        material_id=material.id,
    )

    db.session.commit()
    return ServiceResult.success(
        notifications=notifications,
        item=item,
        ticket=ticket,
    )


def request_ticket_closure(ticket: LabTicket, actor_user: User) -> ServiceResult:
    if not ticket:
        message = "Ticket no encontrado."
        _log_ticket_rejected(
            action="LAB_TICKET_CLOSE_REQUEST_REJECTED",
            actor_user=actor_user,
            ticket=ticket,
            reason=message,
        )
        return ServiceResult.failure(message)
    if ticket.status == LabTicketStatus.CLOSURE_REQUESTED:
        message = "El ticket ya tiene una solicitud de cierre pendiente."
        _log_ticket_rejected(
            action="LAB_TICKET_CLOSE_REQUEST_REJECTED",
            actor_user=actor_user,
            ticket=ticket,
            reason=message,
        )
        return ServiceResult.failure(message)
    if ticket.status == LabTicketStatus.CLOSED:
        message = "El ticket ya está cerrado."
        _log_ticket_rejected(
            action="LAB_TICKET_CLOSE_REQUEST_REJECTED",
            actor_user=actor_user,
            ticket=ticket,
            reason=message,
        )
        return ServiceResult.failure(message)
    if ticket.status == LabTicketStatus.CLOSED_WITH_DEBT:
        message = "El ticket ya está cerrado con adeudo."
        _log_ticket_rejected(
            action="LAB_TICKET_CLOSE_REQUEST_REJECTED",
            actor_user=actor_user,
            ticket=ticket,
            reason=message,
        )
        return ServiceResult.failure(message)

    updated_rows = (
        LabTicket.query
        .filter(LabTicket.id == ticket.id)
        .filter(LabTicket.status.in_([LabTicketStatus.OPEN, LabTicketStatus.READY_FOR_PICKUP]))
        .update({LabTicket.status: LabTicketStatus.CLOSURE_REQUESTED}, synchronize_session=False)
    )
    if updated_rows == 0:
        db.session.refresh(ticket)
        message = f"El ticket no se puede operar desde estado {ticket.status}."
        _log_ticket_rejected(
            action="LAB_TICKET_CLOSE_REQUEST_REJECTED",
            actor_user=actor_user,
            ticket=ticket,
            reason=message,
        )
        return ServiceResult.failure(message)

    db.session.refresh(ticket)

    admins = User.query.filter(User.role.in_(["ADMIN", "SUPERADMIN"])).all()
    notifications = []
    for admin in admins:
        notif = Notification(
            user_id=admin.id,
            title="Solicitud de cierre de ticket",
            message=f"{actor_user.email} solicitó el cierre del ticket #{ticket.id}.",
            link=url_for("reservations.admin_ticket_detail", ticket_id=ticket.id),
        )
        db.session.add(notif)
        notifications.append(notif)

    log_event(
        module="LAB_TICKETS",
        action="LAB_TICKET_CLOSE_REQUESTED_BY_USER",
        user_id=actor_user.id,
        entity_label=f"LabTicket #{ticket.id}",
        description=f"Usuario solicitó cierre de ticket #{ticket.id}",
        metadata={"ticket_id": ticket.id, "reservation_id": ticket.reservation_id},
    )
    db.session.commit()

    return ServiceResult.success(
        message="Solicitud de cierre enviada.",
        ticket=ticket,
        notifications=notifications,
    )


def can_close_ticket(status: str | None) -> bool:
    return is_active_lab_ticket_status(status) or is_lab_ticket_closure_requested(status)


def close_ticket(ticket: LabTicket, actor_user: User) -> ServiceResult:
    if ticket.status == LabTicketStatus.CLOSED:
        message = "El ticket ya está cerrado."
        _log_ticket_rejected(action="LAB_TICKET_CLOSE_REJECTED", actor_user=actor_user, ticket=ticket, reason=message)
        return ServiceResult.failure(message)
    if ticket.status == LabTicketStatus.CLOSED_WITH_DEBT:
        message = "El ticket ya fue cerrado con adeudo."
        _log_ticket_rejected(action="LAB_TICKET_CLOSE_REJECTED", actor_user=actor_user, ticket=ticket, reason=message)
        return ServiceResult.failure(message)
    if not can_close_ticket(ticket.status):
        message = f"El ticket no se puede cerrar desde estado {ticket.status}."
        _log_ticket_rejected(action="LAB_TICKET_CLOSE_REJECTED", actor_user=actor_user, ticket=ticket, reason=message)
        return ServiceResult.failure(message)

    has_missing = False
    created_debt_ids: list[int] = []
    previous_ticket_status = ticket.status

    try:
        for item in ticket.items:
            missing_qty = item.quantity_delivered - item.quantity_returned
            if missing_qty > 0:
                has_missing = True
                item.status = TicketItemStatus.DELIVERED
                debt_result = create_debt_for_ticket(
                    ticket=ticket,
                    item=item,
                    missing_qty=missing_qty,
                    actor_user_id=actor_user.id,
                )
                if not debt_result.ok:
                    db.session.rollback()
                    message = debt_result.message or "No se pudo generar el adeudo durante el cierre del ticket."
                    _log_ticket_rejected(
                        action="LAB_TICKET_CLOSE_REJECTED",
                        actor_user=actor_user,
                        ticket=ticket,
                        reason=message,
                    )
                    return ServiceResult.failure(message)
                debt = debt_result.data.get("debt") if debt_result.ok else None
                if debt_result.ok and debt_result.data.get("created") and debt:
                    created_debt_ids.append(debt.id)

        ticket.status = LabTicketStatus.CLOSED_WITH_DEBT if has_missing else LabTicketStatus.CLOSED
        ticket.closed_by_user_id = actor_user.id
        ticket.closed_at = datetime.now()

        close_notification = Notification(
            user_id=ticket.owner_user_id,
            title="Ticket de reservación cerrado",
            message=f"Tu ticket #{ticket.id} se cerró con estado {ticket.status}.",
            link=url_for("reservations.my_reservations"),
        )
        db.session.add(close_notification)

        admin_notifications: list[Notification] = []
        if created_debt_ids:
            admins = User.query.filter(User.role.in_(["ADMIN", "SUPERADMIN"])).all()
            for admin in admins:
                notif = Notification(
                    user_id=admin.id,
                    title="Adeudo generado por cierre de ticket",
                    message=f"El ticket #{ticket.id} cerró con adeudo. Revisa deudor y seguimiento.",
                    link=url_for("debts.admin_list"),
                )
                db.session.add(notif)
                admin_notifications.append(notif)

        log_event(
            module="LAB_TICKETS",
            action="LAB_TICKET_CLOSED",
            user_id=actor_user.id,
            entity_label=f"LabTicket #{ticket.id}",
            description=f"Ticket #{ticket.id} cerrado con estado {ticket.status}",
            metadata={
                "ticket_id": ticket.id,
                "entity_id": ticket.id,
                "result": "success",
                "owner_user_id": ticket.owner_user_id,
                "previous_status": previous_ticket_status,
                "new_status": ticket.status,
                "created_debt_ids": created_debt_ids,
            },
        )

        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        logger.exception(
            "Error cerrando ticket con posible generación de adeudo",
            extra={"ticket_id": getattr(ticket, "id", None), "actor_user_id": getattr(actor_user, "id", None)},
        )
        message = f"No se pudo cerrar el ticket ({exc.__class__.__name__})."
        if has_app_context() and current_app.debug:
            message = f"{message} {exc}"
        technical_reason = f"{message} [{exc.__class__.__name__}: {exc}]"
        _log_ticket_rejected(
            action="LAB_TICKET_CLOSE_REJECTED",
            actor_user=actor_user,
            ticket=ticket,
            reason=technical_reason,
        )
        return ServiceResult.failure(message)

    return ServiceResult.success(
        close_notification=close_notification,
        admin_notifications=admin_notifications,
        created_debt_ids=created_debt_ids,
        ticket=ticket,
    )
