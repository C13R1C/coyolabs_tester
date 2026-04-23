import queue

from flask import Blueprint, Response, jsonify, render_template, redirect, request, url_for, flash
from flask_login import current_user
from sqlalchemy.exc import SQLAlchemyError

from app.utils.authz import min_role_required
from app.extensions import db
from app.models.notification import Notification
from app.models.push_subscription import PushSubscription
from app.services.audit_service import log_event
from app.services.notification_realtime_service import (
    get_unread_count,
    heartbeat_payload,
    notification_broker,
    notification_to_dict,
    sse_pack,
)
from app.services.push_service import get_vapid_public_key

notifications_bp = Blueprint("notifications", __name__, url_prefix="/notifications")


@notifications_bp.route("/", methods=["GET"])
@min_role_required("STUDENT")
def list_notifications():
    page = request.args.get("page", 1, type=int) or 1
    per_page = request.args.get("per_page", 50, type=int) or 50
    if per_page < 1:
        per_page = 1
    if per_page > 100:
        per_page = 100

    base_query = (
        Notification.query
        .filter(Notification.user_id == current_user.id)
        .order_by(Notification.created_at.desc())
    )
    total = base_query.order_by(None).count()
    notifications = base_query.offset((page - 1) * per_page).limit(per_page).all()
    total_pages = (total + per_page - 1) // per_page if total else 1

    return render_template(
        "notifications/list.html",
        notifications=notifications,
        page=page,
        per_page=per_page,
        total=total,
        total_pages=total_pages,
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

    try:
        is_persistent = bool(notif.is_persistent)
    except Exception:
        is_persistent = False

    if is_persistent:
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"ok": False, "error": "La notificación permanece activa hasta resolver el perfil pendiente."}), 400
        flash("La notificación permanece activa hasta resolver el perfil pendiente.", "warning")
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
    try:
        updated_rows = (
            Notification.query
            .filter(
                Notification.user_id == current_user.id,
                Notification.is_read.is_(False),
                Notification.is_persistent.is_(False),
            )
            .update({Notification.is_read: True}, synchronize_session=False)
        )
    except SQLAlchemyError:
        db.session.rollback()
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
    try:
        deleted_rows = (
            Notification.query
            .filter(
                Notification.user_id == current_user.id,
                Notification.is_read == True,
                Notification.is_persistent.is_(False),
            )
            .delete(synchronize_session=False)
        )
    except SQLAlchemyError:
        db.session.rollback()
        deleted_rows = (
            Notification.query
            .filter(
                Notification.user_id == current_user.id,
                Notification.is_read == True,
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


@notifications_bp.route("/push/public-key", methods=["GET"], strict_slashes=False)
@min_role_required("STUDENT")
def push_public_key():
    key = get_vapid_public_key()
    if not key:
        return jsonify({"ok": False, "error": "Push no configurado."}), 404
    return jsonify({"ok": True, "public_key": key})


@notifications_bp.route("/push/subscribe", methods=["POST"], strict_slashes=False)
@min_role_required("STUDENT")
def push_subscribe():
    data = request.get_json(silent=True) or {}
    endpoint = (data.get("endpoint") or "").strip()
    keys = data.get("keys") or {}
    p256dh = (keys.get("p256dh") or "").strip()
    auth = (keys.get("auth") or "").strip()

    if not endpoint or not p256dh or not auth:
        return jsonify({"ok": False, "error": "Suscripción inválida."}), 400

    (
        PushSubscription.query
        .filter(PushSubscription.endpoint == endpoint, PushSubscription.user_id != current_user.id)
        .update({PushSubscription.is_active: False}, synchronize_session=False)
    )

    existing = (
        PushSubscription.query
        .filter(PushSubscription.user_id == current_user.id, PushSubscription.endpoint == endpoint)
        .first()
    )
    if existing:
        existing.p256dh = p256dh
        existing.auth = auth
        existing.user_agent = (request.headers.get("User-Agent") or "")[:255] or None
        existing.is_active = True
    else:
        existing = PushSubscription(
            user_id=current_user.id,
            endpoint=endpoint,
            p256dh=p256dh,
            auth=auth,
            user_agent=(request.headers.get("User-Agent") or "")[:255] or None,
            is_active=True,
        )
        db.session.add(existing)

    db.session.commit()
    return jsonify({"ok": True})


@notifications_bp.route("/push/unsubscribe", methods=["POST"], strict_slashes=False)
@min_role_required("STUDENT")
def push_unsubscribe():
    data = request.get_json(silent=True) or {}
    endpoint = (data.get("endpoint") or "").strip()
    if not endpoint:
        return jsonify({"ok": False, "error": "Endpoint requerido."}), 400

    sub = (
        PushSubscription.query
        .filter(PushSubscription.user_id == current_user.id, PushSubscription.endpoint == endpoint)
        .first()
    )
    if sub:
        sub.is_active = False
        db.session.commit()

    return jsonify({"ok": True})
