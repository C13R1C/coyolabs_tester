from math import ceil

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy import func

from app.extensions import db
from app.models.career import Career
from app.models.lab import Lab
from app.models.material import Material
from app.services.audit_service import log_event
from app.utils.authz import min_role_required
from app.utils.roles import ROLE_STUDENT, is_admin_role, normalize_role
from app.utils.text import normalize_spaces



inventory_bp = Blueprint("inventory", __name__, url_prefix="/inventory")

MATERIAL_CATEGORIES = (
    "EQUIPO DE CÓMPUTO",
    "PERIFÉRICO",
    "HERRAMIENTA",
    "INSUMO",
    "INSTRUMENTO DE MEDICIÓN",
    "MATERIAL DE LABORATORIO",
    "MOBILIARIO",
    "OTRO",
)


def _is_inactive_status(status: str | None) -> bool:
    return normalize_spaces(status or "").lower() in {"baja", "de baja", "inactivo"}


def _base_inventory_query(*, include_inactive: bool):
    query = Material.query
    if include_inactive:
        return query

    return query.filter(func.lower(func.coalesce(Material.status, "")) != "baja")


def _apply_student_career_scope(query):
    if normalize_role(current_user.role) != ROLE_STUDENT:
        return query

    if not current_user.career_id:
        return query.filter(Material.id == -1)

    return query.filter(Material.career_id == current_user.career_id)


def _material_payload_from_form(material: Material | None = None) -> tuple[dict, str | None]:
    name = normalize_spaces(request.form.get("name") or "")
    if not name:
        return {}, "El nombre del material es obligatorio."

    lab_id = request.form.get("lab_id", type=int)
    lab = Lab.query.get(lab_id) if lab_id else None
    if not lab:
        return {}, "Selecciona un laboratorio válido."

    career_id = request.form.get("career_id", type=int)
    career = Career.query.get(career_id) if career_id else None
    if not career:
        return {}, "Selecciona una carrera válida."

    pieces_qty_raw = normalize_spaces(request.form.get("pieces_qty") or "")
    pieces_qty = None
    if pieces_qty_raw:
        try:
            pieces_qty = int(pieces_qty_raw)
        except ValueError:
            return {}, "La cantidad de piezas debe ser un número entero."
        if pieces_qty < 0:
            return {}, "La cantidad de piezas no puede ser negativa."
    elif material is None:
        return {}, "La cantidad de piezas es obligatoria y debe ser mayor a 0."

    if material is None and (pieces_qty is None or pieces_qty <= 0):
        return {}, "La cantidad de piezas es obligatoria y debe ser mayor a 0."

    status = normalize_spaces(request.form.get("status") or "")
    if not status:
        status = material.status if material else "Disponible"

    category = normalize_spaces(request.form.get("category") or "").upper()
    if category and category not in MATERIAL_CATEGORIES:
        return {}, "Selecciona una categoría válida."

    tutorial_url = normalize_spaces(request.form.get("tutorial_url") or "")
    if tutorial_url and not (tutorial_url.startswith("http://") or tutorial_url.startswith("https://")):
        return {}, "La URL del tutorial debe iniciar con http:// o https://."

    payload = {
        "lab_id": lab.id,
        "career_id": career.id,
        "name": name,
        "category": category or None,
        "location": normalize_spaces(request.form.get("location") or "") or None,
        "status": status,
        "pieces_text": normalize_spaces(request.form.get("pieces_text") or "") or (str(pieces_qty) if pieces_qty is not None else None),
        "pieces_qty": pieces_qty,
        "brand": normalize_spaces(request.form.get("brand") or "") or None,
        "model": normalize_spaces(request.form.get("model") or "") or None,
        "code": normalize_spaces(request.form.get("code") or "") or None,
        "serial": normalize_spaces(request.form.get("serial") or "") or None,
        "tutorial_url": tutorial_url or None,
        "notes": normalize_spaces(request.form.get("notes") or "") or None,
    }
    return payload, None


def _status_change_reason_requirement(old_status: str | None, new_status: str | None) -> tuple[str | None, str | None]:
    old_is_inactive = _is_inactive_status(old_status)
    new_is_inactive = _is_inactive_status(new_status)
    if old_is_inactive == new_is_inactive:
        return None, None
    if not old_is_inactive and new_is_inactive:
        return "deactivation", "Motivo de baja"
    return "reactivation", "Motivo de reactivación"


@inventory_bp.route("/", methods=["GET"])
@min_role_required("STUDENT")
def inventory_list():
    if normalize_role(current_user.role) == ROLE_STUDENT:
        flash("El módulo de inventario no está disponible para tu rol.", "warning")
        return redirect(url_for("root_home"))

    lab_id = request.args.get("lab_id", type=int)
    career_id = request.args.get("career_id", type=int)
    category = normalize_spaces(request.args.get("category") or "").upper()
    q = (request.args.get("q") or "").strip()
    page = request.args.get("page", type=int) or 1

    include_inactive = bool(request.args.get("include_inactive")) and is_admin_role(current_user.role)

    PER_PAGE = 50
    if page < 1:
        page = 1

    labs = Lab.query.order_by(Lab.name).all()
    careers = Career.query.order_by(Career.name.asc()).all()

    query = _base_inventory_query(include_inactive=include_inactive)
    query = _apply_student_career_scope(query)
    if lab_id:
        query = query.filter(Material.lab_id == lab_id)
    if career_id:
        query = query.filter(Material.career_id == career_id)
    if category:
        query = query.filter(func.upper(func.coalesce(Material.category, "")) == category)

    if q:
        like = f"%{q}%"
        query = query.filter(
            (Material.name.ilike(like)) |
            (Material.location.ilike(like)) |
            (Material.code.ilike(like)) |
            (Material.serial.ilike(like)) |
            (Material.notes.ilike(like))
        )

    # Orden usable
    query = query.order_by(Material.lab_id, Material.location, Material.name)

    total = query.count()
    total_pages = max(1, ceil(total / PER_PAGE))

    if page > total_pages:
        page = total_pages

    materials = query.offset((page - 1) * PER_PAGE).limit(PER_PAGE).all()

    return render_template(
        "inventory/inventory_list.html",
        labs=labs,
        materials=materials,
        selected_lab=lab_id,
        selected_career=career_id,
        selected_category=category,
        categories=MATERIAL_CATEGORIES,
        careers=careers,
        q=q,
        include_inactive=include_inactive,
        page=page,
        total=total,
        total_pages=total_pages,
        per_page=PER_PAGE,
        active_page="inventory",
    )


@inventory_bp.route("/materials/<int:material_id>", methods=["GET"])
@min_role_required("STUDENT")
def material_detail(material_id: int):
    if normalize_role(current_user.role) == ROLE_STUDENT:
        flash("El módulo de inventario no está disponible para tu rol.", "warning")
        return redirect(url_for("root_home"))

    m = Material.query.get(material_id)
    if not m:
        abort(404)
    if _is_inactive_status(m.status) and not is_admin_role(current_user.role):
        flash("Este material no está disponible para consulta pública.", "warning")
        return redirect(url_for("inventory.inventory_list"))
    if normalize_role(current_user.role) == ROLE_STUDENT and m.career_id != current_user.career_id:
        flash("No tienes acceso a materiales de otra carrera.", "error")
        return redirect(url_for("inventory.inventory_list"))
    return render_template("inventory/material_detail.html", material=m, active_page="inventory")


@inventory_bp.route("/admin/new", methods=["GET", "POST"])
@min_role_required("ADMIN")
def admin_new_material():
    labs = Lab.query.order_by(Lab.name).all()
    careers = Career.query.order_by(Career.name.asc()).all()
    form_data = {}

    if request.method == "POST":
        payload, error = _material_payload_from_form()
        form_data = dict(request.form)
        if error:
            flash(error, "error")
            return render_template(
                "inventory/admin_form.html",
                material=None,
                labs=labs,
                careers=careers,
                categories=MATERIAL_CATEGORIES,
                form_data=form_data,
                active_page="inventory",
            )

        material = Material(**payload)
        db.session.add(material)
        db.session.flush()
        log_event(
            module="INVENTORY",
            action="MATERIAL_CREATED",
            user_id=current_user.id,
            material_id=material.id,
            entity_label=f"Material #{material.id}",
            description=f"Material creado: {material.name}",
            metadata={
                "material_id": material.id,
                "lab_id": material.lab_id,
                "career_id": material.career_id,
                "status": material.status,
                "category": material.category,
            },
        )
        db.session.commit()
        flash("Material creado correctamente.", "success")
        return redirect(url_for("inventory.material_detail", material_id=material.id))

    return render_template(
        "inventory/admin_form.html",
        material=None,
        labs=labs,
        careers=careers,
        categories=MATERIAL_CATEGORIES,
        form_data=form_data,
        active_page="inventory",
    )


@inventory_bp.route("/admin/<int:material_id>/edit", methods=["GET", "POST"])
@min_role_required("ADMIN")
def admin_edit_material(material_id: int):
    material = Material.query.get_or_404(material_id)
    labs = Lab.query.order_by(Lab.name).all()
    careers = Career.query.order_by(Career.name.asc()).all()
    form_data = {}

    if request.method == "POST":
        payload, error = _material_payload_from_form(material)
        form_data = dict(request.form)
        reason_value = normalize_spaces(request.form.get("status_change_reason") or "")

        reason_type, reason_label = _status_change_reason_requirement(material.status, payload.get("status") if payload else None)
        if not error and reason_type and not reason_value:
            error = f"Debes indicar {reason_label.lower()}."

        if error:
            flash(error, "error")
            return render_template(
                "inventory/admin_form.html",
                material=material,
                labs=labs,
                careers=careers,
                categories=MATERIAL_CATEGORIES,
                form_data=form_data,
                active_page="inventory",
            )

        old_status = material.status
        for key, value in payload.items():
            setattr(material, key, value)

        log_event(
            module="INVENTORY",
            action="MATERIAL_UPDATED",
            user_id=current_user.id,
            material_id=material.id,
            entity_label=f"Material #{material.id}",
            description=f"Material actualizado: {material.name}",
            metadata={
                "material_id": material.id,
                "career_id": material.career_id,
                "old_status": old_status,
                "new_status": material.status,
                "category": material.category,
                "status_change_reason": reason_value or None,
                "status_change_reason_type": reason_type,
            },
        )
        db.session.commit()
        flash("Material actualizado correctamente.", "success")
        return redirect(url_for("inventory.material_detail", material_id=material.id))

    return render_template(
        "inventory/admin_form.html",
        material=material,
        labs=labs,
        careers=careers,
        categories=MATERIAL_CATEGORIES,
        form_data=form_data,
        active_page="inventory",
    )


@inventory_bp.route("/admin/<int:material_id>/toggle-active", methods=["POST"])
@min_role_required("ADMIN")
def admin_toggle_material_active(material_id: int):
    material = Material.query.get_or_404(material_id)
    reason = normalize_spaces(request.form.get("reason") or "")
    is_reactivating = _is_inactive_status(material.status)

    if not is_reactivating and not reason:
        flash("Debes indicar un motivo para dar de baja este material.", "error")
        return redirect(url_for("inventory.material_detail", material_id=material.id))

    if is_reactivating:
        previous_status = material.status
        material.status = "Disponible"
        action = "MATERIAL_REACTIVATED"
        description = f"Material reactivado: {material.name}"
    else:
        previous_status = material.status
        material.status = "Baja"
        action = "MATERIAL_DEACTIVATED"
        description = f"Material dado de baja: {material.name}"

    log_event(
        module="INVENTORY",
        action=action,
        user_id=current_user.id,
        material_id=material.id,
        entity_label=f"Material #{material.id}",
        description=description,
        metadata={
            "material_id": material.id,
            "career_id": material.career_id,
            "reason": reason or None,
            "previous_status": previous_status,
            "new_status": material.status,
        },
    )
    db.session.commit()
    flash("Estado del material actualizado.", "success")
    return redirect(url_for("inventory.material_detail", material_id=material.id))

@inventory_bp.route("/admin-check", methods=["GET"])
@min_role_required("STAFF")
def admin_check():
    env = (current_app.config.get("ENV") or "").strip().lower()
    if env not in {"development", "dev", "local", "test", "testing"}:
        abort(404)
    return "OK: STAFF access", 200
