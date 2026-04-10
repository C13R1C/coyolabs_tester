import logging

from app.extensions import db
from app.models.notification import Notification
from app.models.user import User
from app.services.notification_realtime_service import publish_notification_created


def build_notification(*, user_id: int, title: str, message: str, link: str | None = None) -> Notification:
    notification = Notification(
        user_id=user_id,
        title=title.strip(),
        message=message.strip(),
        link=link,
    )
    db.session.add(notification)
    return notification


def notify_roles(*, roles: list[str], title: str, message: str, link: str | None = None) -> list[Notification]:
    users = User.query.filter(User.role.in_(roles)).all()
    notifications: list[Notification] = []
    for user in users:
        notifications.append(
            build_notification(user_id=user.id, title=title, message=message, link=link)
        )
    return notifications


def publish_notifications_safe(
    notifications: list[Notification],
    *,
    logger: logging.Logger,
    event_label: str,
    extra: dict | None = None,
) -> None:
    base_extra = extra or {}
    for notification in notifications:
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
