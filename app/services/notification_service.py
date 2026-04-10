from __future__ import annotations

import logging
from datetime import datetime, timedelta

from app.extensions import db
from app.models.notification import Notification
from app.models.user import User
from app.services.notification_realtime_service import publish_notification_created

NotificationPriority = str  # "high" | "medium" | "low"
DEDUP_SECONDS_DEFAULT = 3


def _normalize_actor(actor_name: str | None) -> str:
    value = (actor_name or "").strip()
    return value or "Administración"


def _compose_context_suffix(
    *,
    entity_name: str | None = None,
    time_range: str | None = None,
    extra_context: str | None = None,
) -> str:
    parts: list[str] = []
    if (entity_name or "").strip():
        parts.append((entity_name or "").strip())
    if (time_range or "").strip():
        parts.append((time_range or "").strip())
    if (extra_context or "").strip():
        parts.append((extra_context or "").strip())
    return f" ({' · '.join(parts)})" if parts else ""


def _dedupe_recent_notification(
    *,
    user_id: int,
    title: str,
    message: str,
    link: str | None,
    dedup_seconds: int,
) -> bool:
    if dedup_seconds <= 0:
        return False
    cutoff = datetime.utcnow() - timedelta(seconds=dedup_seconds)
    recent = (
        Notification.query
        .filter(Notification.user_id == user_id)
        .filter(Notification.title == title.strip())
        .filter(Notification.message == message.strip())
        .filter(Notification.link == link)
        .filter(Notification.created_at >= cutoff)
        .order_by(Notification.id.desc())
        .first()
    )
    return recent is not None


def _attach_priority(notification: Notification, priority: NotificationPriority) -> Notification:
    setattr(notification, "_priority", (priority or "medium").strip().lower())
    return notification


def build_notification(
    *,
    user_id: int,
    title: str,
    message: str,
    link: str | None = None,
    actor_name: str | None = None,
    entity_name: str | None = None,
    time_range: str | None = None,
    extra_context: str | None = None,
    priority: NotificationPriority = "medium",
    dedup_seconds: int = DEDUP_SECONDS_DEFAULT,
) -> Notification | None:
    actor = _normalize_actor(actor_name) if actor_name is not None else ""
    suffix = _compose_context_suffix(
        entity_name=entity_name,
        time_range=time_range,
        extra_context=extra_context,
    )
    rendered_message = message.strip()
    if actor:
        rendered_message = f"{rendered_message} por {actor}"
    rendered_message = f"{rendered_message}{suffix}".strip()

    if _dedupe_recent_notification(
        user_id=user_id,
        title=title,
        message=rendered_message,
        link=link,
        dedup_seconds=dedup_seconds,
    ):
        return None

    notification = Notification(
        user_id=user_id,
        title=title.strip(),
        message=rendered_message,
        link=link,
    )
    db.session.add(notification)
    return _attach_priority(notification, priority)


def notify_roles(
    *,
    roles: list[str],
    title: str,
    message: str,
    link: str | None = None,
    actor_name: str | None = None,
    entity_name: str | None = None,
    time_range: str | None = None,
    extra_context: str | None = None,
    priority: NotificationPriority = "medium",
    dedup_seconds: int = DEDUP_SECONDS_DEFAULT,
) -> list[Notification]:
    users = User.query.filter(User.role.in_(roles)).all()
    notifications: list[Notification] = []
    for user in users:
        notif = build_notification(
            user_id=user.id,
            title=title,
            message=message,
            link=link,
            actor_name=actor_name,
            entity_name=entity_name,
            time_range=time_range,
            extra_context=extra_context,
            priority=priority,
            dedup_seconds=dedup_seconds,
        )
        if notif is not None:
            notifications.append(notif)
    return notifications


def build_reservation_message(event: str, *, actor_name: str, room: str, time_range: str | None = None) -> str:
    actor = _normalize_actor(actor_name)
    if event == "created":
        return f"Nueva reservación recibida de {actor}"
    if event == "approved":
        return f"Tu reservación fue aprobada por {actor} en {room}{f' ({time_range})' if time_range else ''}"
    if event == "rejected":
        return f"Tu reservación fue rechazada por {actor} en {room}{f' ({time_range})' if time_range else ''}"
    return f"Tu reservación fue actualizada por {actor} en {room}{f' ({time_range})' if time_range else ''}"


def build_debt_message(event: str, *, actor_name: str, debt_id: int, amount_label: str | None = None) -> str:
    actor = _normalize_actor(actor_name)
    if event == "created":
        return f"Se generó un adeudo (folio #{debt_id}) por {actor}{f' por {amount_label}' if amount_label else ''}"
    if event == "resolved":
        return f"Tu adeudo #{debt_id} fue resuelto por {actor}"
    if event == "partial":
        return f"Tu adeudo #{debt_id} recibió un abono por {actor}{f' ({amount_label})' if amount_label else ''}"
    return f"Tu adeudo #{debt_id} fue actualizado por {actor}"


def build_3d_message(event: str, *, actor_name: str, job_id: int, title: str) -> str:
    actor = _normalize_actor(actor_name)
    if event == "created":
        return f"Nueva solicitud de impresión 3D de {actor} (folio #{job_id}: {title})"
    if event == "ready":
        return f"Tu impresión 3D #{job_id} ({title}) está lista. Actualizada por {actor}"
    if event == "canceled":
        return f"Tu impresión 3D #{job_id} ({title}) fue cancelada por {actor}"
    return f"Tu impresión 3D #{job_id} ({title}) fue actualizada por {actor}"


def publish_notifications_safe(
    notifications: list[Notification | None],
    *,
    logger: logging.Logger,
    event_label: str,
    extra: dict | None = None,
) -> None:
    base_extra = extra or {}
    for notification in notifications:
        if notification is None:
            continue
        try:
            publish_notification_created(notification)
        except Exception:
            logger.warning(
                "SSE publish failed after %s",
                event_label,
                exc_info=True,
                extra={
                    **base_extra,
                    "notification_id": notification.id,
                    "target_user_id": notification.user_id,
                },
            )
