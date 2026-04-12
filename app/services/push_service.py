from __future__ import annotations

import json
import logging

from flask import current_app

from app.extensions import db
from app.models.notification import Notification
from app.models.push_subscription import PushSubscription

logger = logging.getLogger(__name__)


def get_vapid_public_key() -> str | None:
    value = (current_app.config.get("VAPID_PUBLIC_KEY") or "").strip()
    return value or None


def _can_send_push() -> bool:
    return bool(
        (current_app.config.get("VAPID_PUBLIC_KEY") or "").strip()
        and (current_app.config.get("VAPID_PRIVATE_KEY") or "").strip()
        and (current_app.config.get("VAPID_CLAIMS_SUBJECT") or "").strip()
    )


def _push_payload(notification: Notification) -> dict:
    return {
        "title": (notification.title or "Notificación").strip(),
        "body": (notification.message or "").strip(),
        "url": notification.link if (notification.link or "").startswith("/") else "/notifications",
        "notification_id": notification.id,
    }


def dispatch_push_for_notification(notification: Notification) -> int:
    """
    Send web push to all active subscriptions for target user.
    Returns number of successful deliveries.
    """
    if not _can_send_push():
        return 0

    try:
        from pywebpush import WebPushException, webpush
    except Exception:
        logger.warning("pywebpush no está disponible; push deshabilitado.")
        return 0

    subscriptions = (
        PushSubscription.query
        .filter(PushSubscription.user_id == notification.user_id, PushSubscription.is_active.is_(True))
        .all()
    )
    if not subscriptions:
        return 0

    payload = json.dumps(_push_payload(notification), ensure_ascii=False)
    vapid_private_key = (current_app.config.get("VAPID_PRIVATE_KEY") or "").strip()
    vapid_claims = {"sub": (current_app.config.get("VAPID_CLAIMS_SUBJECT") or "").strip()}

    sent = 0
    has_deactivations = False
    for sub in subscriptions:
        subscription_info = {
            "endpoint": sub.endpoint,
            "keys": {
                "p256dh": sub.p256dh,
                "auth": sub.auth,
            },
        }
        try:
            webpush(
                subscription_info=subscription_info,
                data=payload,
                vapid_private_key=vapid_private_key,
                vapid_claims=vapid_claims,
            )
            sent += 1
        except WebPushException as exc:
            status_code = getattr(getattr(exc, "response", None), "status_code", None)
            if status_code in {404, 410}:
                sub.is_active = False
                has_deactivations = True
            logger.warning("Falló envío push", exc_info=True)
        except Exception:
            logger.warning("Falló envío push", exc_info=True)

    if has_deactivations:
        db.session.commit()

    return sent
