from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user

from app.constants import ROLE_PENDING
from app.extensions import db
from app.models.notification import Notification
from app.models.critical_action_request import CriticalActionRequest
from app.models.user import User
from app.services.audit_service import log_event
from app.services.notification_realtime_service import publish_notification_created
from app.utils.authz import min_role_required
from app.utils.roles import (
    ROLE_ADMIN,
    ROLE_STAFF,
    ROLE_STUDENT,
    ROLE_SUPERADMIN,
    ROLE_TEACHER,
    normalize_role,
)
from app.utils.validators import is_valid_utpn_email

users_bp = Blueprint("users", __name__, url_prefix="/users")
PENDING_APPROVAL_ROLES = (ROLE_STUDENT, ROLE_TEACHER, ROLE_STAFF, ROLE_ADMIN, ROLE_SUPERADMIN)
ADMIN_PANEL_ROLE_FILTERS = (ROLE_STUDENT, ROLE_TEACHER, ROLE_STAFF, ROLE_ADMIN, ROLE_SUPERADMIN)
SUPERADMIN_ASSIGNABLE_ROLES = (ROLE_STUDENT, ROLE_TEACHER, ROLE_STAFF, ROLE_ADMIN)
ROOT_SUPERADMIN_ASSIGNABLE_ROLES = (ROLE_STUDENT, ROLE_TEACHER, ROLE_STAFF, ROLE_ADMIN, ROLE_SUPERADMIN)
ADMIN_ASSIGNABLE_ROLES = (ROLE_STUDENT, ROLE_TEACHER, ROLE_STAFF)
STAFF_PENDING_ASSIGNABLE_ROLES = (ROLE_TEACHER, ROLE_STAFF)
ADMIN_PENDING_ASSIGNABLE_ROLES = (ROLE_TEACHER, ROLE_STAFF)
CRITICAL_ACTION_TYPES = {
    "DISABLE_USER": "desactivar usuario",
    "ENABLE_USER": "reactivar usuario",
    "BAN_USER": "bloquear usuario",
    "UNBAN_USER": "desbloquear usuario",
    "PROMOTE_TO_ADMIN": "promover a administrador",
}


def _is_superadmin() -> bool:
    return normalize_role(current_user.role) == ROLE_SUPERADMIN


def _root_superadmin_user() -> User | None:
    flagged_root = (
        User.query
        .filter(User.role == ROLE_SUPERADMIN, User.is_root_superadmin.is_(True))
        .order_by(User.id.asc())
        .first()
    )
    if flagged_root:
        return flagged_root

    return (
        User.query
        .filter(User.role == ROLE_SUPERADMIN)
        .order_by(User.created_at.asc(), User.id.asc())
        .first()
    )


def _is_root_superadmin_user(user: User | None) -> bool:
    if not user or normalize_role(user.role) != ROLE_SUPERADMIN:
        return False

    root = _root_superadmin_user()
    if not root:
        return False
    return root.id == user.id


def _is_current_root_superadmin() -> bool:
    if not _is_superadmin():
        return False
    return _is_root_superadmin_user(current_user)


def _is_admin_or_superadmin() -> bool:
    role = normalize_role(current_user.role)
    return role in {ROLE_ADMIN, ROLE_SUPERADMIN}


def _pending_assignable_roles() -> tuple[str, ...]:
    role = normalize_role(current_user.role)
    if role == ROLE_ADMIN:
        return ADMIN_PENDING_ASSIGNABLE_ROLES
    if role == ROLE_SUPERADMIN:
        return ROOT_SUPERADMIN_ASSIGNABLE_ROLES if _is_current_root_superadmin() else SUPERADMIN_ASSIGNABLE_ROLES
    return STAFF_PENDING_ASSIGNABLE_ROLES


def _can_assign_pending_role(new_role: str | None) -> bool:
    return new_role in _pending_assignable_roles()


def _log_admin_event(action: str, description: str, metadata: dict | None = None) -> None:
    log_event(
        module="USERS",
        action=action,
        user_id=current_user.id,
        entity_label=f"AdminAction by {current_user.email}",
        description=description,
        metadata=metadata,
    )


def _create_critical_action_request(target_user: User, action_type: str, reason: str | None = None) -> None:
    pending = (
        CriticalActionRequest.query
        .filter(CriticalActionRequest.requester_id == current_user.id)
        .filter(CriticalActionRequest.target_user_id == target_user.id)
        .filter(CriticalActionRequest.action_type == action_type)
        .filter(CriticalActionRequest.status == "PENDING")
        .first()
    )
    if pending:
        flash("Ya existe una solicitud crítica pendiente para este usuario y acción.", "warning")
        return

    req = CriticalActionRequest(
        requester_id=current_user.id,
        target_user_id=target_user.id,
        action_type=action_type,
        reason=reason or None,
        status="PENDING",
    )
    db.session.add(req)

    superadmins = User.query.filter(User.role == ROLE_SUPERADMIN).all()
    notifications_created: list[Notification] = []
    for superadmin in superadmins:
        notif = Notification(
            user_id=superadmin.id,
            title="Nueva solicitud de acción crítica",
            message=f"{current_user.email} solicitó {CRITICAL_ACTION_TYPES.get(action_type, action_type)} para {target_user.email}.",
            link=url_for("users.critical_action_requests"),
        )
        db.session.add(notif)
        notifications_created.append(notif)

    _log_admin_event(
        action="CRITICAL_ACTION_REQUEST_CREATED",
        description=f"{current_user.email} creó solicitud crítica para {target_user.email}",
        metadata={"target_user_id": target_user.id, "action_type": action_type},
    )
    db.session.commit()
    for notif in notifications_created:
        publish_notification_created(notif)
    flash("Solicitud crítica enviada a SUPERADMIN para aprobación.", "info")


def _block_if_target_is_root_superadmin(target_user: User) -> bool:
    if _is_root_superadmin_user(target_user) and not _is_current_root_superadmin():
        flash("Solo el SUPERADMIN padre puede operar sobre esa cuenta.", "error")
        return True
    return False


def _apply_critical_action(req: CriticalActionRequest) -> str:
    target = User.query.get(req.target_user_id)
    if not target:
        return "Usuario objetivo no encontrado."

    action_type = req.action_type
    if action_type == "DISABLE_USER":
        target.is_active = False
    elif action_type == "ENABLE_USER":
        target.is_active = True
    elif action_type == "BAN_USER":
        target.is_banned = True
    elif action_type == "UNBAN_USER":
        target.is_banned = False
    else:
        return "Tipo de acción crítica no soportado."

    return ""


@users_bp.route("/pending", methods=["GET"])
@min_role_required("ADMIN")
def pending_users():
    users = (
        User.query.filter(User.role == ROLE_PENDING)
        .order_by(User.created_at.asc())
        .all()
    )
    return render_template(
        "users/pending_list.html",
        users=users,
        assignable_roles=_pending_assignable_roles(),
        active_page="users",
    )


@users_bp.route("/<int:user_id>/role", methods=["POST"])
@min_role_required("ADMIN")
def assign_role(user_id: int):
    if not _is_admin_or_superadmin():
        flash("Solo ADMIN/SUPERADMIN puede cambiar roles pendientes.", "error")
        return redirect(url_for("users.admin_panel"))

    user = User.query.get_or_404(user_id)
    new_role = normalize_role(request.form.get("role"))

    if not _can_assign_pending_role(new_role):
        if new_role in {ROLE_ADMIN, ROLE_SUPERADMIN}:
            flash("Solo SUPERADMIN puede asignar ese rol.", "error")
        else:
            flash("Rol no permitido para tu nivel de acceso.", "error")
        return redirect(url_for("users.pending_users"))

    if new_role not in PENDING_APPROVAL_ROLES:
        flash("Rol no permitido para asignación administrativa.", "error")
        return redirect(url_for("users.pending_users"))

    old_role = user.role
    user.role = new_role
    if old_role == ROLE_PENDING:
        (
            Notification.query
            .filter(
                Notification.event_code == "PENDING_PROFILE",
                Notification.related_user_id == user.id,
                Notification.is_persistent.is_(True),
            )
            .update(
                {
                    Notification.is_persistent: False,
                    Notification.is_read: True,
                },
                synchronize_session=False,
            )
        )
    _log_admin_event(
        action="USER_ROLE_UPDATED",
        description=f"{current_user.email} cambió rol de {user.email}",
        metadata={"user_id": user.id, "old_role": old_role, "new_role": new_role},
    )
    db.session.commit()

    flash(f"Rol actualizado a {new_role} para {user.email}.", "success")
    return redirect(url_for("users.pending_users"))


@users_bp.route("/admin", methods=["GET"])
@min_role_required("ADMIN")
def admin_panel():
    if not _is_admin_or_superadmin():
        flash("No autorizado.", "error")
        return redirect(url_for("root_home"))

    q = (request.args.get("q") or "").strip()
    role = normalize_role(request.args.get("role"))

    query = User.query.filter(User.role != ROLE_PENDING)

    if q:
        like = f"%{q.lower()}%"
        query = query.filter(
            db.or_(
                db.func.lower(User.email).like(like),
                db.func.lower(db.func.coalesce(User.full_name, "")).like(like),
                db.func.lower(db.func.coalesce(User.matricula, "")).like(like),
            )
        )

    if role in ADMIN_PANEL_ROLE_FILTERS:
        query = query.filter(User.role == role)

    users = query.order_by(User.created_at.desc()).limit(300).all()
    pending_review_count = User.query.filter(User.role == ROLE_PENDING).count()

    assignable_roles = ROOT_SUPERADMIN_ASSIGNABLE_ROLES if _is_current_root_superadmin() else (
        SUPERADMIN_ASSIGNABLE_ROLES if _is_superadmin() else ADMIN_ASSIGNABLE_ROLES
    )
    root_superadmin = _root_superadmin_user()

    return render_template(
        "users/admin_panel.html",
        users=users,
        q=q,
        selected_role=role or "",
        role_filters=ADMIN_PANEL_ROLE_FILTERS,
        assignable_roles=assignable_roles,
        is_superadmin=_is_superadmin(),
        is_root_superadmin=_is_current_root_superadmin(),
        root_superadmin_id=root_superadmin.id if root_superadmin else None,
        pending_review_count=pending_review_count,
        active_page="users",
    )


@users_bp.route("/admin/profile-change-requests", methods=["GET"])
@min_role_required("ADMIN")
def profile_change_requests():
    flash("El flujo de solicitudes de perfil fue retirado del sistema operativo.", "info")
    return redirect(url_for("users.create_admin_account"))


@users_bp.route("/admin/critical-action-requests", methods=["GET"])
@min_role_required("ADMIN")
def critical_action_requests():
    pending_accounts = (
        User.query
        .filter(User.role == ROLE_PENDING)
        .order_by(User.created_at.asc())
        .limit(300)
        .all()
    )

    query = CriticalActionRequest.query
    if not _is_superadmin():
        query = query.filter(CriticalActionRequest.requester_id == current_user.id)

    critical_requests = (
        query.order_by(
            db.case((CriticalActionRequest.status == "PENDING", 0), else_=1),
            CriticalActionRequest.created_at.desc(),
        )
        .limit(300)
        .all()
    )
    return render_template(
        "users/critical_action_requests.html",
        requests=critical_requests,
        pending_accounts=pending_accounts,
        pending_accounts_assignable_roles=_pending_assignable_roles(),
        is_superadmin=_is_superadmin(),
        action_labels=CRITICAL_ACTION_TYPES,
        active_page="users",
    )


@users_bp.route("/admin/critical-action-requests/<int:request_id>/approve", methods=["POST"])
@min_role_required("SUPERADMIN")
def approve_critical_action_request(request_id: int):
    if not _is_superadmin():
        flash("Solo SUPERADMIN puede aprobar acciones críticas.", "error")
        return redirect(url_for("users.admin_panel"))

    req = CriticalActionRequest.query.get_or_404(request_id)
    target_user = User.query.get(req.target_user_id)
    if target_user and _is_root_superadmin_user(target_user) and not _is_current_root_superadmin():
        flash("Solo el SUPERADMIN padre puede aprobar acciones sobre esa cuenta.", "error")
        return redirect(url_for("users.critical_action_requests"))
    if req.status != "PENDING":
        flash("La solicitud ya fue procesada.", "warning")
        return redirect(url_for("users.critical_action_requests"))

    error = _apply_critical_action(req)
    if error:
        flash(error, "error")
        return redirect(url_for("users.critical_action_requests"))

    req.status = "APPROVED"
    req.reviewed_by = current_user.id
    req.reviewed_at = db.func.now()

    requester_notification = Notification(
        user_id=req.requester_id,
        title="Solicitud crítica aprobada",
        message=f"La acción {CRITICAL_ACTION_TYPES.get(req.action_type, req.action_type)} fue aprobada por SUPERADMIN.",
        link=url_for("users.critical_action_requests"),
    )
    db.session.add(requester_notification)
    _log_admin_event(
        action="CRITICAL_ACTION_REQUEST_APPROVED",
        description=f"{current_user.email} aprobó solicitud crítica #{req.id}",
        metadata={"request_id": req.id, "target_user_id": req.target_user_id, "action_type": req.action_type},
    )
    db.session.commit()
    publish_notification_created(requester_notification)
    flash("Solicitud crítica aprobada y aplicada.", "success")
    return redirect(url_for("users.critical_action_requests"))


@users_bp.route("/admin/critical-action-requests/<int:request_id>/reject", methods=["POST"])
@min_role_required("SUPERADMIN")
def reject_critical_action_request(request_id: int):
    if not _is_superadmin():
        flash("Solo SUPERADMIN puede rechazar acciones críticas.", "error")
        return redirect(url_for("users.admin_panel"))

    req = CriticalActionRequest.query.get_or_404(request_id)
    target_user = User.query.get(req.target_user_id)
    if target_user and _is_root_superadmin_user(target_user) and not _is_current_root_superadmin():
        flash("Solo el SUPERADMIN padre puede rechazar acciones sobre esa cuenta.", "error")
        return redirect(url_for("users.critical_action_requests"))
    if req.status != "PENDING":
        flash("La solicitud ya fue procesada.", "warning")
        return redirect(url_for("users.critical_action_requests"))

    req.status = "REJECTED"
    req.reviewed_by = current_user.id
    req.reviewed_at = db.func.now()

    requester_notification = Notification(
        user_id=req.requester_id,
        title="Solicitud crítica rechazada",
        message=f"La acción {CRITICAL_ACTION_TYPES.get(req.action_type, req.action_type)} fue rechazada por SUPERADMIN.",
        link=url_for("users.critical_action_requests"),
    )
    db.session.add(requester_notification)
    _log_admin_event(
        action="CRITICAL_ACTION_REQUEST_REJECTED",
        description=f"{current_user.email} rechazó solicitud crítica #{req.id}",
        metadata={"request_id": req.id, "target_user_id": req.target_user_id, "action_type": req.action_type},
    )
    db.session.commit()
    publish_notification_created(requester_notification)
    flash("Solicitud crítica rechazada.", "success")
    return redirect(url_for("users.critical_action_requests"))


@users_bp.route("/admin/profile-change-requests/<int:request_id>/approve", methods=["POST"])
@min_role_required("ADMIN")
def approve_profile_change_request(request_id: int):
    flash("El flujo de solicitudes de perfil fue retirado del sistema operativo.", "info")
    return redirect(url_for("users.create_admin_account"))


@users_bp.route("/admin/profile-change-requests/<int:request_id>/reject", methods=["POST"])
@min_role_required("ADMIN")
def reject_profile_change_request(request_id: int):
    flash("El flujo de solicitudes de perfil fue retirado del sistema operativo.", "info")
    return redirect(url_for("users.create_admin_account"))


@users_bp.route("/admin/create-admin", methods=["GET", "POST"])
@min_role_required("ADMIN")
def create_admin_account():
    if not _is_admin_or_superadmin():
        flash("No autorizado.", "error")
        return redirect(url_for("users.admin_panel"))

    if request.method == "POST":
        action = (request.form.get("action") or "").strip()
        if action == "change_role":
            if not _is_superadmin():
                flash("Solo SUPERADMIN puede cambiar roles existentes.", "error")
                return redirect(url_for("users.create_admin_account"))

            selected_user_id = request.form.get("user_id", type=int)
            requested_role = normalize_role(request.form.get("role"))
            assignable_roles = ROOT_SUPERADMIN_ASSIGNABLE_ROLES if _is_current_root_superadmin() else SUPERADMIN_ASSIGNABLE_ROLES
            if not selected_user_id or requested_role not in assignable_roles:
                flash("Cambio de rol inválido.", "error")
                return redirect(url_for("users.create_admin_account"))

            user_to_update = User.query.get_or_404(selected_user_id)
            target_role = normalize_role(user_to_update.role)
            if target_role == ROLE_SUPERADMIN:
                flash("No se permite modificar cuentas SUPERADMIN desde este flujo.", "error")
                return redirect(url_for("users.create_admin_account"))

            old_role = user_to_update.role
            user_to_update.role = requested_role
            _log_admin_event(
                action="USER_ROLE_CHANGED_BY_SUPERADMIN",
                description=f"{current_user.email} cambió rol de {user_to_update.email} a {requested_role}",
                metadata={"user_id": user_to_update.id, "old_role": old_role, "new_role": requested_role},
            )
            db.session.commit()
            flash("Rol actualizado.", "success")
            return redirect(url_for("users.create_admin_account"))

        flash("Acción no válida.", "error")
        return redirect(url_for("users.create_admin_account"))

    eligible_users = []
    if _is_superadmin():
        eligible_users = (
            User.query
            .order_by(User.full_name.asc(), User.email.asc())
            .all()
        )
    pending_accounts = (
        User.query
        .filter(User.role == ROLE_PENDING)
        .order_by(User.created_at.asc())
        .all()
    )

    return render_template(
        "users/create_admin.html",
        eligible_users=eligible_users,
        pending_accounts=pending_accounts,
        pending_accounts_assignable_roles=_pending_assignable_roles(),
        is_superadmin=_is_superadmin(),
        is_root_superadmin=_is_current_root_superadmin(),
        active_page="users",
    )


@users_bp.route("/admin/<int:user_id>/update", methods=["POST"])
@min_role_required("ADMIN")
def admin_update_user(user_id: int):
    user = User.query.get_or_404(user_id)

    actor_is_superadmin = _is_superadmin()
    target_role = normalize_role(user.role)

    if target_role == ROLE_SUPERADMIN and not actor_is_superadmin:
        flash("No puedes editar una cuenta SUPERADMIN.", "error")
        return redirect(url_for("users.admin_panel"))

    if (target_role in {ROLE_ADMIN, ROLE_SUPERADMIN}) and not actor_is_superadmin:
        flash("Solo SUPERADMIN puede editar cuentas administrativas.", "error")
        return redirect(url_for("users.admin_panel"))

    target_is_root_superadmin = _is_root_superadmin_user(user)
    if target_is_root_superadmin and not _is_current_root_superadmin():
        flash("Solo el SUPERADMIN padre puede modificar esa cuenta.", "error")
        return redirect(url_for("users.admin_panel"))

    if actor_is_superadmin and user.id == current_user.id:
        requested_active = request.form.get("is_active") == "1"
        requested_banned = request.form.get("is_banned") == "1"
        if not requested_active or requested_banned:
            flash("No puedes desactivarte o bloquearte a ti mismo.", "error")
            return redirect(url_for("users.admin_panel"))

    old_data = {
        "email": user.email,
        "full_name": user.full_name,
        "matricula": user.matricula,
        "phone": user.phone,
        "role": user.role,
        "is_active": user.is_active,
        "is_banned": user.is_banned,
    }

    new_email = (request.form.get("email") or "").strip().lower()
    if not new_email:
        flash("El email es obligatorio.", "error")
        return redirect(url_for("users.admin_panel"))
    if not is_valid_utpn_email(new_email):
        flash("Solo se permiten correos institucionales (@utpn.edu.mx)", "error")
        return redirect(url_for("users.admin_panel"))

    existing = User.query.filter(User.email == new_email, User.id != user.id).first()
    if existing:
        flash("Ya existe otro usuario con ese email.", "error")
        return redirect(url_for("users.admin_panel"))

    user.email = new_email
    user.full_name = (request.form.get("full_name") or "").strip() or None
    user.matricula = (request.form.get("matricula") or "").strip() or None
    user.phone = (request.form.get("phone") or "").strip() or None

    requested_role = normalize_role(request.form.get("role"))
    assignable = ROOT_SUPERADMIN_ASSIGNABLE_ROLES if _is_current_root_superadmin() else (
        SUPERADMIN_ASSIGNABLE_ROLES if actor_is_superadmin else ADMIN_ASSIGNABLE_ROLES
    )
    if not actor_is_superadmin and requested_role != normalize_role(user.role):
        flash("Solo SUPERADMIN puede cambiar roles.", "error")
        return redirect(url_for("users.admin_panel"))
    if target_is_root_superadmin and requested_role != ROLE_SUPERADMIN:
        flash("No puedes degradar al SUPERADMIN padre.", "error")
        return redirect(url_for("users.admin_panel"))
    if target_role == ROLE_SUPERADMIN and requested_role != ROLE_SUPERADMIN and not _is_current_root_superadmin():
        flash("Solo el SUPERADMIN padre puede revocar rol SUPERADMIN.", "error")
        return redirect(url_for("users.admin_panel"))
    if requested_role in assignable:
        user.role = requested_role

    user.is_active = request.form.get("is_active") == "1"
    user.is_banned = request.form.get("is_banned") == "1"

    _log_admin_event(
        action="USER_UPDATED",
        description=f"{current_user.email} actualizó usuario {user.email}",
        metadata={"user_id": user.id, "old": old_data, "new_role": user.role},
    )
    db.session.commit()

    flash("Usuario actualizado.", "success")
    return redirect(url_for("users.admin_panel"))


@users_bp.route("/admin/<int:user_id>/disable", methods=["POST"])
@min_role_required("ADMIN")
def admin_disable_user(user_id: int):
    user = User.query.get_or_404(user_id)
    if _block_if_target_is_root_superadmin(user):
        return redirect(url_for("users.admin_panel"))

    if normalize_role(user.role) == ROLE_SUPERADMIN and not _is_superadmin():
        _create_critical_action_request(user, "DISABLE_USER")
        return redirect(url_for("users.admin_panel"))

    if normalize_role(user.role) == ROLE_ADMIN and not _is_superadmin():
        _create_critical_action_request(user, "DISABLE_USER")
        return redirect(url_for("users.admin_panel"))

    if user.id == current_user.id and _is_superadmin():
        flash("No puedes desactivarte a ti mismo.", "error")
        return redirect(url_for("users.admin_panel"))

    user.is_active = False
    _log_admin_event(
        action="USER_DISABLED",
        description=f"{current_user.email} desactivó a {user.email}",
        metadata={"user_id": user.id},
    )
    db.session.commit()

    flash("Usuario desactivado.", "success")
    return redirect(url_for("users.admin_panel"))


@users_bp.route("/admin/<int:user_id>/enable", methods=["POST"])
@min_role_required("ADMIN")
def admin_enable_user(user_id: int):
    user = User.query.get_or_404(user_id)
    if _block_if_target_is_root_superadmin(user):
        return redirect(url_for("users.admin_panel"))

    if normalize_role(user.role) == ROLE_SUPERADMIN and not _is_superadmin():
        _create_critical_action_request(user, "ENABLE_USER")
        return redirect(url_for("users.admin_panel"))

    if normalize_role(user.role) == ROLE_ADMIN and not _is_superadmin():
        _create_critical_action_request(user, "ENABLE_USER")
        return redirect(url_for("users.admin_panel"))

    user.is_active = True
    _log_admin_event(
        action="USER_ENABLED",
        description=f"{current_user.email} reactivó a {user.email}",
        metadata={"user_id": user.id},
    )
    db.session.commit()

    flash("Usuario reactivado.", "success")
    return redirect(url_for("users.admin_panel"))


@users_bp.route("/admin/<int:user_id>/ban", methods=["POST"])
@min_role_required("ADMIN")
def admin_ban_user(user_id: int):
    user = User.query.get_or_404(user_id)
    if _block_if_target_is_root_superadmin(user):
        return redirect(url_for("users.admin_panel"))

    if normalize_role(user.role) == ROLE_SUPERADMIN and not _is_superadmin():
        _create_critical_action_request(user, "BAN_USER")
        return redirect(url_for("users.admin_panel"))

    if normalize_role(user.role) == ROLE_ADMIN and not _is_superadmin():
        _create_critical_action_request(user, "BAN_USER")
        return redirect(url_for("users.admin_panel"))

    if user.id == current_user.id and _is_superadmin():
        flash("No puedes bloquearte a ti mismo.", "error")
        return redirect(url_for("users.admin_panel"))

    user.is_banned = True
    _log_admin_event(
        action="USER_BANNED",
        description=f"{current_user.email} bloqueó a {user.email}",
        metadata={"user_id": user.id},
    )
    db.session.commit()

    flash("Usuario bloqueado.", "success")
    return redirect(url_for("users.admin_panel"))


@users_bp.route("/admin/<int:user_id>/unban", methods=["POST"])
@min_role_required("ADMIN")
def admin_unban_user(user_id: int):
    user = User.query.get_or_404(user_id)
    if _block_if_target_is_root_superadmin(user):
        return redirect(url_for("users.admin_panel"))

    if normalize_role(user.role) == ROLE_SUPERADMIN and not _is_superadmin():
        _create_critical_action_request(user, "UNBAN_USER")
        return redirect(url_for("users.admin_panel"))

    if normalize_role(user.role) == ROLE_ADMIN and not _is_superadmin():
        _create_critical_action_request(user, "UNBAN_USER")
        return redirect(url_for("users.admin_panel"))

    user.is_banned = False
    _log_admin_event(
        action="USER_UNBANNED",
        description=f"{current_user.email} desbloqueó a {user.email}",
        metadata={"user_id": user.id},
    )
    db.session.commit()

    flash("Usuario desbloqueado.", "success")
    return redirect(url_for("users.admin_panel"))


@users_bp.route("/admin/<int:user_id>/delete", methods=["POST"])
@min_role_required("SUPERADMIN")
def superadmin_soft_delete_admin(user_id: int):
    if not _is_superadmin():
        flash("Solo SUPERADMIN puede realizar esta acción.", "error")
        return redirect(url_for("users.admin_panel"))

    user = User.query.get_or_404(user_id)
    target_role = normalize_role(user.role)
    target_is_root_superadmin = _is_root_superadmin_user(user)

    if target_role == ROLE_SUPERADMIN:
        if target_is_root_superadmin:
            flash("No se permite eliminar al SUPERADMIN padre.", "error")
            return redirect(url_for("users.admin_panel"))
        if not _is_current_root_superadmin():
            flash("Solo el SUPERADMIN padre puede eliminar otros SUPERADMIN.", "error")
            return redirect(url_for("users.admin_panel"))

    if user.id == current_user.id:
        flash("No puedes autoeliminarte.", "error")
        return redirect(url_for("users.admin_panel"))

    user.is_active = False
    user.is_banned = True
    _log_admin_event(
        action="USER_SOFT_DELETED",
        description=f"{current_user.email} desactivó usuario {user.email}",
        metadata={"user_id": user.id, "target_role": target_role},
    )
    db.session.commit()

    flash("Usuario desactivado (soft delete).", "success")
    return redirect(url_for("users.admin_panel"))
