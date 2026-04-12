import json
import logging
import queue
import threading
from datetime import datetime

from app.models.notification import Notification
from app.services.push_service import dispatch_push_for_notification


class NotificationBroker:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._subscribers: dict[int, list[queue.Queue]] = {}

    def subscribe(self, user_id: int) -> queue.Queue:
        q: queue.Queue = queue.Queue(maxsize=100)
        with self._lock:
            self._subscribers.setdefault(user_id, []).append(q)
        return q

    def unsubscribe(self, user_id: int, q: queue.Queue) -> None:
        with self._lock:
            queues = self._subscribers.get(user_id, [])
            if q in queues:
                queues.remove(q)
            if not queues and user_id in self._subscribers:
                del self._subscribers[user_id]

    def publish(self, user_id: int, event_name: str, payload: dict) -> None:
        with self._lock:
            queues = list(self._subscribers.get(user_id, []))

        for q in queues:
            try:
                q.put_nowait((event_name, payload))
            except queue.Full:
                continue


notification_broker = NotificationBroker()
_logger = logging.getLogger(__name__)
_warned_single_process_delivery = False


def _warn_single_process_delivery_once() -> None:
    global _warned_single_process_delivery
    if _warned_single_process_delivery:
        return
    _warned_single_process_delivery = True
    _logger.warning(
        "SSE notification broker is process-local; in multi-worker deployments, "
        "clients connected to other workers may not receive events."
    )


def get_unread_count(user_id: int) -> int:
    return (
        Notification.query
        .filter(Notification.user_id == user_id, Notification.is_read.is_(False))
        .count()
    )


def notification_to_dict(notification: Notification, unread_count: int | None = None) -> dict:
    if unread_count is None:
        unread_count = get_unread_count(notification.user_id)

    priority = getattr(notification, "_priority", None)
    if not priority:
        text = f"{notification.title} {notification.message}".lower()
        if any(word in text for word in ["adeudo", "rechaz", "bloque", "cancel"]):
            priority = "high"
        elif any(word in text for word in ["aprob", "actualiz", "lista", "listo", "resuelto"]):
            priority = "medium"
        else:
            priority = "low"

    return {
        "id": notification.id,
        "title": notification.title,
        "message": notification.message,
        "link": notification.link,
        "event_code": getattr(notification, "event_code", None),
        "is_persistent": bool(getattr(notification, "is_persistent", False)),
        "priority": priority,
        "is_read": notification.is_read,
        "created_at": notification.created_at.isoformat() if notification.created_at else None,
        "created_at_label": notification.created_at.strftime("%d/%m/%Y %H:%M") if notification.created_at else "",
        "unread_count": unread_count,
    }


def publish_notification_created(notification: Notification) -> None:
    _warn_single_process_delivery_once()
    unread_count = get_unread_count(notification.user_id)
    payload = notification_to_dict(notification, unread_count=unread_count)
    notification_broker.publish(notification.user_id, "notification_created", payload)
    try:
        dispatch_push_for_notification(notification)
    except Exception:
        _logger.warning("Web push dispatch failed", exc_info=True)


def sse_pack(event_name: str, payload: dict) -> str:
    return f"event: {event_name}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def heartbeat_payload() -> dict:
    return {"ts": datetime.utcnow().isoformat() + "Z"}
