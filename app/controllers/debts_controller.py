import logging
import uuid

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


def _parse_debt_items_from_form() -> list[dict]:
    material_ids = request.form.getlist("item_material_id")
    quantities = request.form.getlist("item_amount")
    parsed_items: list[dict] = []

    for index, (material_raw, qty_raw) in enumerate(zip(material_ids, quantities), start=1):
        if not (material_raw or "").strip() and not (qty_raw or "").strip():
            continue
        try:
            material_id = int(material_raw)
            amount = int(qty_raw)
        except (TypeError, ValueError):
            raise ValueError(f"Item {index}: material y cantidad deben ser números enteros.")
        if amount < 1:
            raise ValueError(f"Item {index}: la cantidad debe ser mayor o igual a 1.")
        material = Material.query.get(material_id)
        if not material:
            raise ValueError(f"Item {index}: material_id no existe.")
        parsed_items.append({"material": material, "amount": amount})
    return parsed_items


def _debt_amounts(debt: Debt) -> tuple[int, int]:
    original = int((debt.original_amount if debt.original_amount is not None else debt.amount) or 0)
    pending = int((debt.remaining_amount if debt.remaining_amount is not None else debt.amount) or 0)
    return original, pending


def _build_admin_debt_rows(debts: list[Debt]) -> list[dict]:
    grouped_by_case: dict[tuple[str, int], list[Debt]] = {}
    for debt in debts:
        if debt.case_code:
            grouped_by_case.setdefault((debt.case_code, debt.user_id), []).append(debt)

    rows: list[dict] = []
    consumed_ids: set[int] = set()

    for debt in debts:
        if debt.id in consumed_ids:
            continue

        if debt.case_code:
            case_key = (debt.case_code, debt.user_id)
            case_items = grouped_by_case.get(case_key, [])
            if len(case_items) > 1:
                for item in case_items:
                    consumed_ids.add(item.id)

                total_original = 0
                total_pending = 0
                for item in case_items:
                    item_original, item_pending = _debt_amounts(item)
                    total_original += item_original
                    total_pending += item_pending

                rows.append({
                    "row_type": "group",
                    "id_label": f"CASO-{debt.case_code[:8]}",
                    "detail_debt_id": case_items[0].id,
                    "user": case_items[0].user,
                    "status": DebtStatus.PENDING if total_pending > 0 else DebtStatus.PAID,
                    "materials_count": len(case_items),
                    "material_label": f"{len(case_items)} materiales",
                    "total_original": total_original,
                    "total_pending": total_pending,
                    "reason": next((item.reason for item in case_items if item.reason), "-"),
                    "flow_label": "Conjunto",
                    "can_pay_from_list": False,
                    "payment_debt_id": None,
                    "payment_max": 0,
                })
                continue

        consumed_ids.add(debt.id)
        original, pending = _debt_amounts(debt)
        rows.append({
            "row_type": "single",
            "id_label": str(debt.id),
            "detail_debt_id": debt.id,
            "user": debt.user,
            "status": DebtStatus.PENDING if pending > 0 else DebtStatus.PAID,
            "materials_count": 1,
            "material_label": f"{debt.material.name} ({debt.material.id})" if debt.material else "-",
            "total_original": original,
            "total_pending": pending,
            "reason": debt.reason or "-",
            "flow_label": "Singular",
            "can_pay_from_list": pending > 0,
            "payment_debt_id": debt.id,
            "payment_max": pending,
        })

    return rows


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

    debt_rows = _build_admin_debt_rows(debts)

    users_with_debts = len({row["user"].id for row in debt_rows if row.get("user")})

    return render_template(
        "debts/admin_list.html",
        debts=debts,
        debt_rows=debt_rows,
        users_with_debts=users_with_debts,
        active_page="debts"
    )


# -------------------------
# CREAR ADEUDO (SOLO ADMIN REAL)
# -------------------------
@debts_bp.route("/admin/create", methods=["GET", "POST"])
@min_role_required("ADMIN")
@permission_required("debts.create")
def admin_create():
    materials = Material.query.order_by(Material.name.asc()).limit(500).all()
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        reason = (request.form.get("reason") or "").strip()

        user = User.query.filter_by(email=email).first()
        if not user:
            flash("No existe un usuario con ese correo.", "error")
            return redirect(url_for("debts.admin_create"))

        try:
            parsed_items = _parse_debt_items_from_form()
        except ValueError as exc:
            flash(str(exc), "error")
            return redirect(url_for("debts.admin_create"))

        if not parsed_items:
            material_id = request.form.get("material_id", type=int)
            amount = request.form.get("amount", type=int)
            material = None
            if material_id:
                material = Material.query.get(material_id)
                if not material:
                    flash("material_id no existe.", "error")
                    return redirect(url_for("debts.admin_create"))
            parsed_items = [{"material": material, "amount": amount if amount is not None else 1}]

        case_code = str(uuid.uuid4()) if len(parsed_items) > 1 else None
        created_debts: list[Debt] = []
        for item in parsed_items:
            debt = Debt(
                user_id=user.id,
                material_id=item["material"].id if item["material"] else None,
                status=DebtStatus.PENDING,
                reason=reason or None,
                amount=item["amount"],
                original_amount=item["amount"],
                remaining_amount=item["amount"],
                case_code=case_code,
            )
            db.session.add(debt)
            db.session.flush()
            created_debts.append(debt)
            _log_debt_event(
                action="DEBT_CREATED",
                debt=debt,
                description=f"Adeudo creado para {user.email}",
                metadata={"reason": debt.reason, "case_code": case_code},
            )

        first_debt = created_debts[0]
        total_pending = sum(int(d.remaining_amount or d.amount or 0) for d in created_debts)
        user_notification = Notification(
            user_id=user.id,
            title="Se generó un adeudo" if len(created_debts) == 1 else "Se generó un adeudo conjunto",
            message=(
                f"Se registró {'un adeudo' if len(created_debts) == 1 else f'un adeudo de {len(created_debts)} materiales'} "
                f"({total_pending} pendiente total)."
                f"{f' Motivo: {reason}.' if reason else ''}"
            ),
            link=url_for("debts.my_debts"),
        )
        db.session.add(user_notification)
        db.session.commit()
        try:
            publish_notification_created(user_notification)
        except Exception:
            logger.warning(
                "SSE publish failed after debt creation",
                extra={"debt_id": first_debt.id, "notification_id": user_notification.id, "target_user_id": user_notification.user_id},
            )

        flash("Adeudo creado." if len(created_debts) == 1 else "Adeudo conjunto creado.", "success")
        return redirect(url_for("debts.admin_detail", debt_id=first_debt.id))

    return render_template("debts/admin_create.html", active_page="debts", materials=materials)


@debts_bp.route("/admin/<int:debt_id>", methods=["GET"])
@min_role_required("STAFF")
@permission_required("debts.view_all")
def admin_detail(debt_id: int):
    debt = (
        Debt.query
        .options(joinedload(Debt.user), joinedload(Debt.material))
        .get(debt_id)
    )
    if not debt:
        flash("Adeudo no encontrado.", "error")
        return redirect(url_for("debts.admin_list"))

    case_debts: list[Debt]
    if debt.case_code:
        case_debts = (
            Debt.query
            .options(joinedload(Debt.user), joinedload(Debt.material))
            .filter(Debt.case_code == debt.case_code, Debt.user_id == debt.user_id)
            .order_by(Debt.id.asc())
            .all()
        )
    else:
        case_debts = [debt]

    total_original = sum(int((d.original_amount if d.original_amount is not None else d.amount) or 0) for d in case_debts)
    total_pending = sum(int((d.remaining_amount if d.remaining_amount is not None else d.amount) or 0) for d in case_debts)
    case_status = DebtStatus.PAID if total_pending == 0 else DebtStatus.PENDING
    case_flow = "Conjunto" if len(case_debts) > 1 else "Singular"

    return render_template(
        "debts/admin_detail.html",
        debt=debt,
        case_debts=case_debts,
        total_original=total_original,
        total_pending=total_pending,
        case_status=case_status,
        case_flow=case_flow,
        active_page="debts",
    )


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

    payment_amount = (request.form.get("payment_amount") or "").strip()
    parsed_payment = payment_amount if payment_amount else None

    result = resolve_debt(debt=debt, actor_user=current_user, payment_amount=parsed_payment)
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

    if result.data.get("paid_in_full"):
        flash("Adeudo marcado como pagado.", "success")
    else:
        flash(
            f"Abono registrado. Pendiente actual: {int(result.data.get('remaining_amount'))}.",
            "success",
        )
    return_to = (request.form.get("return_to") or "").strip().lower()
    if return_to == "detail":
        return redirect(url_for("debts.admin_detail", debt_id=debt.id))
    return redirect(url_for("debts.admin_list"))
