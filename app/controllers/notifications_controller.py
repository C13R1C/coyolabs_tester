import queue

from flask import Blueprint, Response, jsonify, render_template, redirect, request, url_for, flash
from flask_login import current_user

from app.utils.authz import min_role_required
from app.extensions import db
from app.models.notification import Notification
from app.services.audit_service import log_event
from app.services.notification_realtime_service import (
    get_unread_count,
    heartbeat_payload,
    notification_broker,
    notification_to_dict,
    sse_pack,
)

notifications_bp = Blueprint("notifications", __name__, url_prefix="/notifications")


@notifications_bp.route("/", methods=["GET"])
@min_role_required("STUDENT")
def list_notifications():
    notifications = (
        Notification.query
        .filter(Notification.user_id == current_user.id)
        .order_by(Notification.created_at.desc())
        .all()
    )

    return render_template(
        "notifications/list.html",
        notifications=notifications,
        active_page="notifications"
    )


@notifications_bp.route("/feed", methods=["GET"])
@min_role_required("STUDENT")
def feed_notifications():
    notifications = (
        Notification.query
        .filter(Notification.user_id == current_user.id)
        .order_by(Notification.created_at.desc())
        .limit(5)
        .all()
    )
    unread_count = get_unread_count(current_user.id)
    return jsonify({
        "notifications": [notification_to_dict(n, unread_count=unread_count) for n in notifications],
        "unread_count": unread_count,
    })


@notifications_bp.route("/stream", methods=["GET"])
@min_role_required("STUDENT")
def stream_notifications():
    user_id = current_user.id

    def generate():
        subscription = notification_broker.subscribe(user_id)
        try:
            yield sse_pack("connected", {"ok": True})
            while True:
                try:
                    event_name, payload = subscription.get(timeout=25)
                    yield sse_pack(event_name, payload)
                except queue.Empty:
                    yield sse_pack("heartbeat", heartbeat_payload())
        finally:
            notification_broker.unsubscribe(user_id, subscription)

    response = Response(generate(), mimetype="text/event-stream")
    response.headers["Cache-Control"] = "no-cache"
    response.headers["X-Accel-Buffering"] = "no"
    return response


@notifications_bp.route("/<int:notif_id>/read", methods=["POST"])
@min_role_required("STUDENT")
def mark_read(notif_id: int):
    notif = Notification.query.get(notif_id)

    if not notif or notif.user_id != current_user.id:
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"ok": False, "error": "Notificación no encontrada."}), 404
        flash("Notificación no encontrada.", "error")
        return redirect(url_for("notifications.list_notifications"))

    notif.is_read = True
    log_event(
        module="NOTIFICATIONS",
        action="NOTIFICATION_MARKED_READ",
        user_id=current_user.id,
        entity_label=f"Notification #{notif.id}",
        description="Usuario marcó notificación como leída",
        metadata={"notification_id": notif.id, "entity_id": notif.id, "result": "success"},
    )
    db.session.commit()
    unread_count = get_unread_count(current_user.id)

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"ok": True, "unread_count": unread_count})

    if notif.link and notif.link.startswith("/"):
        return redirect(notif.link)

    return redirect(url_for("notifications.list_notifications"))


@notifications_bp.route("/mark-all-read", methods=["POST"])
@min_role_required("STUDENT")
def mark_all_read():
    updated_rows = (
        Notification.query
        .filter(Notification.user_id == current_user.id, Notification.is_read.is_(False))
        .update({Notification.is_read: True}, synchronize_session=False)
    )
    db.session.commit()
    unread_count = get_unread_count(current_user.id)

    return jsonify({
        "ok": True,
        "updated": int(updated_rows or 0),
        "unread_count": unread_count,
    })


@notifications_bp.route("/clear-read", methods=["POST"])
@min_role_required("STUDENT")
def clear_read():
    deleted_rows = (
        Notification.query
        .filter(
            Notification.user_id == current_user.id,
            Notification.is_read == True
        )
        .delete(synchronize_session=False)
    )

    db.session.commit()

    unread_count = get_unread_count(current_user.id)

    return jsonify({
        "ok": True,
        "deleted": int(deleted_rows or 0),
        "unread_count": unread_count,
    })
