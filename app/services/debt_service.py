from dataclasses import dataclass, field
from typing import Any

from flask import url_for
from sqlalchemy import and_, or_

from app.extensions import db
from app.models.debt import Debt
from app.models.lab_ticket import LabTicket
from app.models.notification import Notification
from app.models.ticket_item import TicketItem
from app.models.user import User
from app.services.audit_service import log_event
from app.utils.statuses import DebtStatus, LabTicketStatus


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


def _log_debt_rejected(action: str, actor_user: User | None, debt: Debt | None, reason: str) -> None:
    debt_id = getattr(debt, "id", None)
    log_event(
        module="DEBTS",
        action=action,
        user_id=getattr(actor_user, "id", None),
        entity_label=f"Debt #{debt_id or 'N/A'}",
        description=reason,
        metadata={
            "debt_id": debt_id,
            "entity_id": debt_id,
            "target_user_id": getattr(debt, "user_id", None),
            "result": "rejected",
            "reason": reason,
            "status": getattr(debt, "status", None),
        },
        material_id=getattr(debt, "material_id", None),
    )


def user_has_open_debts(user_id: int) -> bool:
    return (
        Debt.query
        .filter(Debt.user_id == user_id, Debt.status == DebtStatus.PENDING)
        .count()
        > 0
    )


def create_debt_for_ticket(ticket: LabTicket, item: TicketItem, missing_qty: int, actor_user_id: int | None) -> ServiceResult:
    existing_debt = (
        Debt.query
        .filter(
            Debt.user_id == ticket.owner_user_id,
            Debt.material_id == item.material_id,
            Debt.status == DebtStatus.PENDING,
            or_(
                Debt.ticket_id == ticket.id,
                Debt.ticket_id.is_(None),
            ),
        )
        .order_by(Debt.id.desc())
        .first()
    )
    if existing_debt:
        if existing_debt.ticket_id is None:
            existing_debt.ticket_id = ticket.id
        return ServiceResult.success(debt=existing_debt, created=False)

    missing = max(0, missing_qty)
    if missing <= 0:
        return ServiceResult.success(created=False)

    material_name = item.material.name if item.material else f"Material ID {item.material_id}"

    debt = Debt(
        user_id=ticket.owner_user_id,
        material_id=item.material_id,
        ticket_id=ticket.id,
        status=DebtStatus.PENDING,
        reason=f"Faltante de {missing} unidad(es) en ticket #{ticket.id} - {material_name}",
        amount=missing,
    )
    db.session.add(debt)
    db.session.flush()

    log_event(
        module="DEBTS",
        action="DEBT_CREATED",
        user_id=actor_user_id,
        entity_label=f"Debt #{debt.id}",
        description=f"Adeudo generado automáticamente por faltante en ticket #{ticket.id}",
        metadata={
            "debt_id": debt.id,
            "entity_id": debt.id,
            "result": "success",
            "ticket_id": ticket.id,
            "target_user_id": ticket.owner_user_id,
            "material_id": item.material_id,
            "missing_qty": missing,
            "origin": "LAB_TICKET_CLOSE",
        },
        material_id=item.material_id,
    )
    return ServiceResult.success(debt=debt, created=True)


def sync_ticket_after_debt_resolution(debt: Debt) -> ServiceResult:
    ticket_id = debt.ticket_id
    if not ticket_id:
        return ServiceResult.success(ticket=None, ticket_closed=False)

    ticket = LabTicket.query.get(ticket_id)
    if not ticket or ticket.owner_user_id != debt.user_id or ticket.status != LabTicketStatus.CLOSED_WITH_DEBT:
        return ServiceResult.success(ticket=None, ticket_closed=False)

    remaining_open_debts = (
        Debt.query
        .filter(Debt.user_id == debt.user_id, Debt.status == DebtStatus.PENDING)
        .filter(
            or_(
                Debt.ticket_id == ticket_id,
                and_(Debt.ticket_id.is_(None), Debt.reason.ilike(f"%ticket #{ticket_id}%")),
            )
        )
        .count()
    )
    if remaining_open_debts == 0:
        ticket.status = LabTicketStatus.CLOSED
        return ServiceResult.success(ticket=ticket, ticket_closed=True)

    return ServiceResult.success(ticket=ticket, ticket_closed=False)


def resolve_debt(debt: Debt, actor_user: User) -> ServiceResult:
    updated_rows = (
        Debt.query
        .filter(Debt.id == debt.id, Debt.status == DebtStatus.PENDING)
        .update(
            {
                Debt.status: DebtStatus.PAID,
                Debt.closed_at: db.func.now(),
            },
            synchronize_session=False,
        )
    )
    if updated_rows == 0:
        db.session.refresh(debt)
        if debt.status == DebtStatus.PAID:
            message = "El adeudo ya fue resuelto."
        else:
            message = f"El adeudo no se puede resolver desde estado {debt.status}."
        _log_debt_rejected("DEBT_CLOSE_REJECTED", actor_user, debt, message)
        return ServiceResult.failure(message)

    db.session.refresh(debt)
    previous_status = DebtStatus.PENDING

    log_event(
        module="DEBTS",
        action="DEBT_CLOSED",
        user_id=actor_user.id,
        entity_label=f"Debt #{debt.id}",
        description=f"Adeudo #{debt.id} marcado como pagado",
        metadata={
            "debt_id": debt.id,
            "entity_id": debt.id,
            "target_user_id": debt.user_id,
            "material_id": debt.material_id,
            "result": "success",
            "status": debt.status,
            "previous_status": previous_status,
            "new_status": debt.status,
        },
        material_id=debt.material_id,
    )

    sync_result = sync_ticket_after_debt_resolution(debt)
    ticket_to_close = sync_result.data.get("ticket") if sync_result.ok else None
    ticket_closed = bool(sync_result.data.get("ticket_closed")) if sync_result.ok else False

    ticket_notification = None
    if ticket_to_close and ticket_closed:
        log_event(
            module="DEBTS",
            action="LAB_TICKET_CORRECTED_AFTER_DEBT",
            user_id=actor_user.id,
            entity_label=f"Debt #{debt.id}",
            description=f"Ticket #{ticket_to_close.id} corregido a CLOSED tras resolver adeudo",
            metadata={
                "debt_id": debt.id,
                "entity_id": debt.id,
                "ticket_id": ticket_to_close.id,
                "target_user_id": debt.user_id,
                "result": "success",
            },
            material_id=debt.material_id,
        )
        ticket_notification = Notification(
            user_id=ticket_to_close.owner_user_id,
            title="Ticket corregido",
            message=f"Tu ticket #{ticket_to_close.id} fue corregido a cerrado tras resolver el adeudo.",
            link=url_for("reservations.my_reservations"),
        )
        db.session.add(ticket_notification)

    admin_notifications = []
    admins = User.query.filter(User.role.in_(["ADMIN", "SUPERADMIN"])).all()
    for admin in admins:
        notif = Notification(
            user_id=admin.id,
            title="Adeudo resuelto",
            message=f"El adeudo #{debt.id} fue marcado como pagado.",
            link=url_for("debts.admin_list"),
        )
        db.session.add(notif)
        admin_notifications.append(notif)

    db.session.commit()
    return ServiceResult.success(
        ticket_notification=ticket_notification,
        admin_notifications=admin_notifications,
        debt=debt,
    )