from flask import url_for

from app.extensions import db
from app.models.notification import Notification
from app.models.reservation import Reservation
from app.models.user import User
from app.services.audit_service import log_event
from app.utils.statuses import ReservationStatus


def approve_reservation(reservation: Reservation, admin_user: User, admin_note: str | None = None) -> Notification:
    reservation.status = ReservationStatus.APPROVED
    reservation.admin_note = (admin_note or "").strip() or None

    approval_notification = Notification(
        user_id=reservation.user_id,
        title="Reservación aprobada",
        message=f"Tu reservación #{reservation.id} fue aprobada.",
        link=url_for("reservations.my_reservations"),
    )
    db.session.add(approval_notification)

    log_event(
        module="RESERVATIONS",
        action="RESERVATION_APPROVED",
        user_id=admin_user.id,
        entity_label=f"Reservation #{reservation.id}",
        description=f"Reserva #{reservation.id} aprobada",
        metadata={"reservation_id": reservation.id, "target_user_id": reservation.user_id},
    )

    db.session.commit()
    return approval_notification


def reject_reservation(reservation: Reservation, admin_user: User, admin_note: str | None = None) -> Notification:
    reservation.status = ReservationStatus.REJECTED
    reservation.admin_note = (admin_note or "").strip() or None

    rejection_notification = Notification(
        user_id=reservation.user_id,
        title="Reservación rechazada",
        message=f"Tu reservación #{reservation.id} fue rechazada.",
        link=url_for("reservations.my_reservations"),
    )
    db.session.add(rejection_notification)

    log_event(
        module="RESERVATIONS",
        action="RESERVATION_REJECTED",
        user_id=admin_user.id,
        entity_label=f"Reservation #{reservation.id}",
        description=f"Reserva #{reservation.id} rechazada",
        metadata={"reservation_id": reservation.id, "target_user_id": reservation.user_id},
    )

    db.session.commit()
    return rejection_notification
