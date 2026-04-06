import logging

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import current_user
from sqlalchemy.orm import joinedload

from app.utils.roles import is_admin_role
from app.utils.authz import min_role_required
from app.utils.permission_required import permission_required

from app.extensions import db
from app.models.debt import Debt
from app.models.notification import Notification
from app.models.user import User
from app.models.material import Material
from app.services.debt_service import resolve_debt
from app.services.audit_service import log_event
from app.services.notification_realtime_service import publish_notification_created
from app.utils.statuses import DebtStatus


debts_bp = Blueprint("debts", __name__, url_prefix="/debts")
logger = logging.getLogger(__name__)


def _log_debt_event(action: str, debt: Debt, description: str, metadata: dict | None = None) -> None:
    payload = {
        "debt_id": debt.id,
        "target_user_id": debt.user_id,
        "material_id": debt.material_id,
        "status": debt.status,
    }
    if metadata:
        payload.update(metadata)

    log_event(
        module="DEBTS",
        action=action,
        user_id=getattr(current_user, "id", None),
        entity_label=f"Debt #{debt.id}",
        description=description,
        metadata=payload,
        material_id=debt.material_id,
    )


# -------------------------
# HOME
# -------------------------
@debts_bp.route("/", methods=["GET"])
@min_role_required("STUDENT")
def debts_home():
    if is_admin_role(current_user.role):
        return redirect(url_for("debts.admin_list"))

    return redirect(url_for("debts.my_debts"))


# -------------------------
# VER ADEUDOS PROPIOS
# -------------------------
@debts_bp.route("/my", methods=["GET"])
@min_role_required("STUDENT")
@permission_required("debts.view_own")
def my_debts():
    debts = (
        Debt.query
        .options(joinedload(Debt.material))
        .filter(Debt.user_id == current_user.id)
        .order_by(Debt.created_at.desc())
        .all()
    )

    return render_template(
        "debts/my_debts.html",
        debts=debts,
        active_page="debts"
    )


# -------------------------
# VER TODOS LOS ADEUDOS
# STAFF = SOLO VER
# -------------------------
@debts_bp.route("/admin", methods=["GET"])
@min_role_required("STAFF")
@permission_required("debts.view_all")
def admin_list():
    debts = (
        Debt.query
        .options(joinedload(Debt.user), joinedload(Debt.material))
        .order_by(Debt.created_at.desc())
        .limit(200)
        .all()
    )

    return render_template(
        "debts/admin_list.html",
        debts=debts,
        active_page="debts"
    )


# -------------------------
# CREAR ADEUDO (SOLO ADMIN REAL)
# -------------------------
@debts_bp.route("/admin/create", methods=["GET", "POST"])
@min_role_required("ADMIN")
@permission_required("debts.create")
def admin_create():
    if request.method == "POST":
        pending_notifications: list[Notification] = []
        email = (request.form.get("email") or "").strip().lower()
        material_id = request.form.get("material_id", type=int)
        reason = (request.form.get("reason") or "").strip()

        user = User.query.filter_by(email=email).first()
        if not user:
            flash("No existe un usuario con ese correo.", "error")
            return redirect(url_for("debts.admin_create"))

        material = None
        if material_id:
            material = Material.query.get(material_id)
            if not material:
                flash("material_id no existe.", "error")
                return redirect(url_for("debts.admin_create"))

        debt = Debt(
            user_id=user.id,
            material_id=material.id if material else None,
            status=DebtStatus.OPEN,
            reason=reason or None,
        )

        db.session.add(debt)
        db.session.flush()

        _log_debt_event(
            action="DEBT_CREATED",
            debt=debt,
            description=f"Adeudo creado para {user.email}",
            metadata={"reason": debt.reason},
        )
        user_notification = Notification(
            user_id=user.id,
            title="Nuevo adeudo registrado",
            message="Se registró un adeudo en tu cuenta. Revisa el detalle en el módulo de adeudos.",
            link=url_for("debts.my_debts"),
        )
        db.session.add(user_notification)
        db.session.commit()
        try:
            publish_notification_created(user_notification)
        except Exception:
            logger.warning(
                "SSE publish failed after debt creation",
                extra={"debt_id": debt.id, "notification_id": user_notification.id, "target_user_id": user_notification.user_id},
            )

        flash("Adeudo creado.", "success")
        return redirect(url_for("debts.admin_list"))

    return render_template("debts/admin_create.html", active_page="debts")


# -------------------------
# CERRAR ADEUDO
# -------------------------
@debts_bp.route("/admin/<int:debt_id>/close", methods=["POST"])
@min_role_required("ADMIN")
@permission_required("debts.close")
def admin_close(debt_id: int):
    debt = Debt.query.get(debt_id)

    if not debt:
        flash("Adeudo no encontrado.", "error")
        return redirect(url_for("debts.admin_list"))

    result = resolve_debt(debt=debt, actor_user=current_user)
    if not result.ok:
        flash(result.message, "error")
        return redirect(url_for("debts.admin_list"))

    ticket_notification = result.data["ticket_notification"]
    admin_notifications = result.data["admin_notifications"]
    if ticket_notification:
        try:
            publish_notification_created(ticket_notification)
        except Exception:
            logger.warning(
                "SSE publish failed after debt resolution (ticket notification)",
                extra={"debt_id": debt.id, "notification_id": ticket_notification.id, "target_user_id": ticket_notification.user_id},
            )
    for admin_notif in admin_notifications:
        try:
            publish_notification_created(admin_notif)
        except Exception:
            logger.warning(
                "SSE publish failed after debt resolution (admin notification)",
                extra={"debt_id": debt.id, "notification_id": admin_notif.id, "target_user_id": admin_notif.user_id},
            )

    flash("Adeudo marcado como pagado.", "success")
    return redirect(url_for("debts.admin_list"))
