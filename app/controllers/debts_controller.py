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
from app.models.user import User
from app.models.material import Material
from app.services.debt_service import resolve_debt
from app.services.audit_service import log_event
from app.services.notification_service import (
    build_debt_message,
    build_notification,
    notify_roles,
    publish_notifications_safe,
)
from app.utils.statuses import DebtStatus


debts_bp = Blueprint("debts", __name__, url_prefix="/debts")
logger = logging.getLogger(__name__)


def _safe_lower(value) -> str:
    return (value or "").lower()


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


def _case_status_from_items(items: list[Debt]) -> str:
    """
    Regla de negocio: un caso conjunto solo está pagado cuando TODOS los items
    tienen pendiente 0. Si al menos uno conserva pendiente > 0, el caso sigue pendiente.
    """
    total_pending = sum(_debt_amounts(item)[1] for item in items)
    return DebtStatus.PENDING if total_pending > 0 else DebtStatus.PAID


def _visible_case_id(prefix: str, seed_id: int) -> str:
    return f"{prefix}-{seed_id:04d}"


def _build_material_preview(items: list[Debt], preview_limit: int = 2) -> str:
    chunks: list[str] = []
    for item in items[:preview_limit]:
        _, pending = _debt_amounts(item)
        material_name = item.material.name if item.material else "Material sin catálogo"
        chunks.append(f"{material_name} x{pending}")
    remaining_count = len(items) - preview_limit
    if remaining_count > 0:
        chunks.append(f"+{remaining_count} más")
    return " · ".join(chunks) if chunks else "-"


def _case_item_progress(items: list[Debt]) -> tuple[int, int, int]:
    total_items = len(items)
    if total_items <= 0:
        return 0, 0, 0
    paid_items = sum(1 for item in items if _debt_amounts(item)[1] == 0)
    progress_pct = round((paid_items / total_items) * 100)
    return paid_items, total_items, progress_pct


def _user_career_name(user: User | None) -> str:
    if not user:
        return ""
    return (user.career_rel.name if user.career_rel else user.career) or ""


def _can_assign_material_to_user(user: User, material: Material | None) -> tuple[bool, str | None]:
    if not material:
        return True, None

    role = (user.role or "").upper()
    if role == "STUDENT":
        if material.career_id is None:
            return True, None
        if not user.career_id:
            return False, f"El alumno {user.email} no tiene carrera asignada y el material '{material.name}' requiere carrera."
        if material.career_id != user.career_id:
            return False, f"El material '{material.name}' no corresponde a la carrera del alumno seleccionado."
        return True, None

    # Docente (y roles administrativos por compatibilidad legacy) puede recibir cualquier material.
    return True, None


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

                case_items_sorted = sorted(case_items, key=lambda x: x.id)
                total_original = 0
                total_pending = 0
                for item in case_items_sorted:
                    item_original, item_pending = _debt_amounts(item)
                    total_original += item_original
                    total_pending += item_pending

                case_status = _case_status_from_items(case_items_sorted)
                case_visible_id = _visible_case_id("ADEUDO-CJ", case_items_sorted[0].id)
                paid_items, total_items, progress_pct = _case_item_progress(case_items_sorted)

                case_material_names = " ".join(
                    _safe_lower(item.material.name if item.material else "")
                    for item in case_items_sorted
                ).strip()
                rows.append({
                    "row_type": "group",
                    "id_label": case_visible_id,
                    "detail_debt_id": case_items_sorted[0].id,
                    "user": case_items_sorted[0].user,
                    "status": case_status,
                    "materials_count": len(case_items_sorted),
                    "material_label": f"{len(case_items_sorted)} materiales",
                    "material_preview": _build_material_preview(case_items_sorted),
                    "paid_items": paid_items,
                    "total_items": total_items,
                    "progress_pct": progress_pct,
                    "total_original": total_original,
                    "total_pending": total_pending,
                    "reason": next((item.reason for item in case_items_sorted if item.reason), "-"),
                    "flow_label": "Conjunto",
                    "can_pay_from_list": False,
                    "payment_debt_id": None,
                    "payment_max": 0,
                    "search_blob": " ".join([
                        _safe_lower(case_visible_id),
                        _safe_lower(case_items_sorted[0].user.email if case_items_sorted[0].user else ""),
                        _safe_lower(case_items_sorted[0].user.full_name if case_items_sorted[0].user else ""),
                        _safe_lower(case_items_sorted[0].user.matricula if case_items_sorted[0].user else ""),
                        _safe_lower(case_status),
                        "conjunto",
                        case_material_names,
                        _safe_lower(next((item.reason for item in case_items_sorted if item.reason), "")),
                    ]).strip(),
                })
                continue

        consumed_ids.add(debt.id)
        original, pending = _debt_amounts(debt)
        visible_id = _visible_case_id("ADEUDO-SG", debt.id)
        singular_material = debt.material.name if debt.material and debt.material.name else "-"
        singular_status = _case_status_from_items([debt])
        rows.append({
            "row_type": "single",
            "id_label": visible_id,
            "detail_debt_id": debt.id,
            "user": debt.user,
            "status": singular_status,
            "materials_count": 1,
            "material_label": f"{singular_material} ({debt.material.id})" if debt.material else "-",
            "material_preview": singular_material,
            "paid_items": 1 if pending == 0 else 0,
            "total_items": 1,
            "progress_pct": 100 if pending == 0 else 0,
            "total_original": original,
            "total_pending": pending,
            "reason": debt.reason or "-",
            "flow_label": "Singular",
            "can_pay_from_list": pending > 0,
            "payment_debt_id": debt.id,
            "payment_max": pending,
            "search_blob": " ".join([
                _safe_lower(visible_id),
                _safe_lower(debt.user.email if debt.user else ""),
                _safe_lower(debt.user.full_name if debt.user else ""),
                _safe_lower(debt.user.matricula if debt.user else ""),
                _safe_lower(singular_status),
                "singular",
                _safe_lower(singular_material),
                _safe_lower(debt.reason),
            ]).strip(),
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
@min_role_required("ADMIN")
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
    debt_records_count = len(debts)
    case_count = len(debt_rows)

    return render_template(
        "debts/admin_list.html",
        debts=debts,
        debt_rows=debt_rows,
        users_with_debts=users_with_debts,
        debt_records_count=debt_records_count,
        case_count=case_count,
        active_page="debts"
    )


# -------------------------
# CREAR ADEUDO (SOLO ADMIN REAL)
# -------------------------
@debts_bp.route("/admin/create", methods=["GET", "POST"])
@min_role_required("ADMIN")
@permission_required("debts.create")
def admin_create():
    materials = Material.query.options(joinedload(Material.career)).order_by(Material.name.asc()).limit(500).all()
    if request.method == "POST":
        user_id = request.form.get("user_id", type=int)
        email = (request.form.get("email") or "").strip().lower()
        reason = (request.form.get("reason") or "").strip()

        user = User.query.get(user_id) if user_id else None
        if not user and email:
            user = User.query.filter_by(email=email).first()
        if not user:
            flash("No existe un usuario con ese correo.", "error")
            return redirect(url_for("debts.admin_create"))

        if (user.role or "").upper() not in {"STUDENT", "TEACHER"}:
            flash("El usuario seleccionado no es válido para asignación de adeudos.", "error")
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

        for item in parsed_items:
            valid, validation_error = _can_assign_material_to_user(user=user, material=item["material"])
            if not valid:
                flash(validation_error or "Material no permitido para el usuario seleccionado.", "error")
                return redirect(url_for("debts.admin_create"))

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
        actor_name = (current_user.full_name or current_user.email or "Administración")
        user_notification = build_notification(
            user_id=user.id,
            title="Se generó un adeudo" if len(created_debts) == 1 else "Se generó un adeudo conjunto",
            message=build_debt_message(
                "created",
                actor_name=actor_name,
                debt_id=first_debt.id,
                amount_label=f"{total_pending} pendiente total",
            ),
            link=url_for("debts.my_debts"),
            entity_name=f"Adeudo #{first_debt.id}",
            extra_context=(reason or None),
            priority="high",
        )
        admin_notifications = notify_roles(
            roles=["ADMIN", "SUPERADMIN", "STAFF"],
            title="Se generó un adeudo",
            message=build_debt_message(
                "created",
                actor_name=actor_name,
                debt_id=first_debt.id,
                amount_label=f"{total_pending} pendiente total",
            ),
            link=url_for("debts.admin_detail", debt_id=first_debt.id),
            entity_name=f"Usuario {user.email}",
            extra_context=(reason or None),
            priority="high",
        )
        db.session.commit()
        notifications_to_publish = [*admin_notifications]
        if user_notification is not None:
            notifications_to_publish.append(user_notification)
        publish_notifications_safe(
            notifications_to_publish,
            logger=logger,
            event_label="debt creation",
            extra={"debt_id": first_debt.id},
        )

        flash("Adeudo creado." if len(created_debts) == 1 else "Adeudo conjunto creado.", "success")
        return redirect(url_for("debts.admin_detail", debt_id=first_debt.id))

    debt_receivers = (
        User.query
        .options(joinedload(User.career_rel))
        .filter(User.role.in_(["STUDENT", "TEACHER"]))
        .order_by(User.full_name.asc(), User.email.asc())
        .limit(1000)
        .all()
    )
    return render_template(
        "debts/admin_create.html",
        active_page="debts",
        materials=materials,
        debt_receivers=debt_receivers,
    )


@debts_bp.route("/admin/<int:debt_id>", methods=["GET"])
@min_role_required("ADMIN")
@permission_required("debts.view_all")
def admin_detail(debt_id: int):
    debt = (
        Debt.query
        .options(joinedload(Debt.user).joinedload(User.career_rel), joinedload(Debt.material))
        .get(debt_id)
    )
    if not debt:
        flash("Adeudo no encontrado.", "error")
        return redirect(url_for("debts.admin_list"))

    case_debts: list[Debt]
    if debt.case_code:
        case_debts = (
            Debt.query
            .options(joinedload(Debt.user).joinedload(User.career_rel), joinedload(Debt.material))
            .filter(Debt.case_code == debt.case_code, Debt.user_id == debt.user_id)
            .order_by(Debt.id.asc())
            .all()
        )
    else:
        case_debts = [debt]

    total_original = sum(int((d.original_amount if d.original_amount is not None else d.amount) or 0) for d in case_debts)
    total_pending = sum(int((d.remaining_amount if d.remaining_amount is not None else d.amount) or 0) for d in case_debts)
    case_status = _case_status_from_items(case_debts)
    case_flow = "Conjunto" if len(case_debts) > 1 else "Singular"
    case_visible_id = _visible_case_id("ADEUDO-CJ", case_debts[0].id) if len(case_debts) > 1 else _visible_case_id("ADEUDO-SG", debt.id)
    paid_items, total_items, progress_pct = _case_item_progress(case_debts)
    user_career_name = _user_career_name(debt.user)


    return render_template(
        "debts/admin_detail.html",
        debt=debt,
        case_debts=case_debts,
        total_original=total_original,
        total_pending=total_pending,
        case_status=case_status,
        case_flow=case_flow,
        case_visible_id=case_visible_id,
        paid_items=paid_items,
        total_items=total_items,
        progress_pct=progress_pct,
        user_career_name=user_career_name,
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
    user_resolution_notification = result.data.get("user_resolution_notification")
    admin_notifications = result.data["admin_notifications"]
    notifications_to_publish = [*admin_notifications]
    if ticket_notification:
        notifications_to_publish.append(ticket_notification)
    if user_resolution_notification:
        notifications_to_publish.append(user_resolution_notification)
    publish_notifications_safe(
        notifications_to_publish,
        logger=logger,
        event_label="debt resolution",
        extra={"debt_id": debt.id},
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
