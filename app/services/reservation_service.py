from datetime import datetime

from flask import url_for

from app.extensions import db
from app.models.reservation import Reservation
from app.models.user import User
from app.services.audit_service import log_event
from app.services.notification_service import build_notification, build_reservation_message
from app.utils.statuses import ReservationStatus


def approve_reservation(reservation: Reservation, admin_user: User, admin_note: str | None = None):
    reservation.status = ReservationStatus.APPROVED
    reservation.admin_note = (admin_note or "").strip() or None

    approval_notification = build_notification(
        user_id=reservation.user_id,
        title="Tu reservación fue aprobada",
        message=build_reservation_message(
            "approved",
            actor_name=(admin_user.full_name or admin_user.email),
            room=reservation.room,
            time_range=f"{reservation.start_time.strftime('%H:%M')} - {reservation.end_time.strftime('%H:%M')}",
        ),
        link=url_for("reservations.my_active_ticket", reservation_id=reservation.id),
        priority="medium",
        dedup_seconds=3,
    )

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


def reject_reservation(reservation: Reservation, admin_user: User, admin_note: str | None = None):
    reservation.status = ReservationStatus.REJECTED
    reservation.admin_note = (admin_note or "").strip() or None

    rejection_notification = build_notification(
        user_id=reservation.user_id,
        title="Tu reservación fue rechazada",
        message=build_reservation_message(
            "rejected",
            actor_name=(admin_user.full_name or admin_user.email),
            room=reservation.room,
            time_range=f"{reservation.start_time.strftime('%H:%M')} - {reservation.end_time.strftime('%H:%M')}",
        ),
        link=url_for("reservations.my_active_ticket", reservation_id=reservation.id),
        priority="high",
        dedup_seconds=3,
    )

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


def expire_unapproved_reservations(now_dt: datetime | None = None) -> int:
    """Auto-cancel pending reservations whose start time has already begun."""
    now = now_dt or datetime.now()
    cancel_reason = "Cancelada por falta de confirmación"

    pending_reservations = (
        Reservation.query
        .filter(Reservation.status == ReservationStatus.PENDING)
        .all()
    )

    expired_count = 0
    for reservation in pending_reservations:
        if not reservation.date or not reservation.start_time:
            continue

        reservation_start = datetime.combine(reservation.date, reservation.start_time)
        if reservation_start > now:
            continue

        reservation.status = ReservationStatus.CANCELLED
        if hasattr(reservation, "admin_note"):
            reservation.admin_note = cancel_reason

        build_notification(
            user_id=reservation.user_id,
            title="Reservación cancelada",
            message="Tu reservación fue cancelada automáticamente por falta de confirmación.",
            link=url_for("reservations.my_reservations"),
            priority="medium",
            dedup_seconds=3,
        )

        log_event(
            module="RESERVATIONS",
            action="RESERVATION_AUTO_CANCELED",
            user_id=None,
            entity_label=f"Reservation #{reservation.id}",
            description="Reservación cancelada automáticamente por falta de confirmación.",
            metadata={"reservation_id": reservation.id, "target_user_id": reservation.user_id},
        )
        expired_count += 1

    if expired_count:
        db.session.commit()

    return expired_count
