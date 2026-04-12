import os
from math import ceil
from uuid import uuid4

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy import func
from werkzeug.utils import secure_filename

from app.extensions import db
from app.models.career import Career
from app.models.lab import Lab
from app.models.material import Material
from app.services.audit_service import log_event
from app.utils.authz import min_role_required
from app.utils.roles import ROLE_STUDENT, is_admin_role, normalize_role
from app.utils.media import resolve_media_url
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


NEW_LOCATION_SENTINEL = "__new__"
ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif"}


def _is_allowed_image(filename: str) -> bool:
    if "." not in (filename or ""):
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in ALLOWED_IMAGE_EXTENSIONS


def _save_material_image(file_storage) -> tuple[str | None, str | None]:
    if not file_storage or not file_storage.filename:
        return None, None
    if not _is_allowed_image(file_storage.filename):
        return None, "Formato de imagen inválido. Usa PNG, JPG, JPEG, WEBP o GIF."

    safe_name = secure_filename(file_storage.filename)
    ext = safe_name.rsplit(".", 1)[1].lower()
    rel_dir = os.path.join("uploads", "materials")
    abs_dir = os.path.join(current_app.root_path, "static", rel_dir)
    os.makedirs(abs_dir, exist_ok=True)

    filename = f"{uuid4().hex}.{ext}"
    abs_path = os.path.join(abs_dir, filename)
    file_storage.save(abs_path)
    return f"{rel_dir}/{filename}", None


def _material_image_src(material: Material | None) -> str | None:
    if not material:
        return None
    image_url = resolve_media_url(material.image_url, ensure_static_file=True)
    if image_url:
        return image_url
    return resolve_media_url(material.image_ref, ensure_static_file=True)


def _normalize_location(value: str | None) -> str:
    normalized = normalize_spaces(value or "")
    if not normalized:
        return ""
    return " ".join(part[:1].upper() + part[1:].lower() for part in normalized.split(" "))


def _existing_location_options(extra_values: list[str] | None = None) -> list[str]:
    rows = (
        db.session.query(Material.location)
        .filter(Material.location.isnot(None))
        .filter(func.trim(Material.location) != "")
        .all()
    )
    unique_locations: dict[str, str] = {}
    for (location_value,) in rows:
        normalized = _normalize_location(location_value)
        if normalized:
            unique_locations[normalized.lower()] = normalized

    for value in extra_values or []:
        normalized = _normalize_location(value)
        if normalized:
            unique_locations.setdefault(normalized.lower(), normalized)

    return sorted(unique_locations.values(), key=str.lower)


def _is_inactive_status(status: str | None) -> bool:
    normalized = normalize_spaces(status or "").lower()
    return normalized in {"baja", "de baja", "inactivo"} or normalized.startswith("baja -")


def _split_tool_status(status: str | None) -> tuple[str, str]:
    normalized = normalize_spaces(status or "")
    lower_value = normalized.lower()
    if " - " in normalized:
        active_state, condition = [part.strip() for part in normalized.split(" - ", 1)]
        active_state = "Alta" if active_state.lower().startswith("alta") else "Baja"
        condition = condition.capitalize()
        if condition not in {"Bueno", "Regular", "Malo"}:
            condition = "Bueno"
        return active_state, condition

    if lower_value in {"disponible", "en mantenimiento"}:
        return "Alta", "Bueno"
    if lower_value == "frágil":
        return "Alta", "Regular"
    if _is_inactive_status(normalized):
        return "Baja", "Regular"
    return "Alta", "Bueno"


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

    lab_id = None
    if material is not None:
        lab_id = request.form.get("lab_id", type=int)
    if not lab_id and material is not None:
        lab_id = material.lab_id
    if not lab_id:
        default_lab = Lab.query.order_by(Lab.id.asc()).first()
        lab_id = default_lab.id if default_lab else None
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

    tool_condition = normalize_spaces(request.form.get("tool_condition") or "")
    active_state = normalize_spaces(request.form.get("active_state") or "")
    if tool_condition and tool_condition not in {"Bueno", "Regular", "Malo"}:
        return {}, "Selecciona una condición válida (Bueno, Regular o Malo)."
    if active_state and active_state not in {"Alta", "Baja"}:
        return {}, "Selecciona un estado válido (Alta o Baja)."

    status = normalize_spaces(request.form.get("status") or "")
    if tool_condition or active_state:
        status = f"{active_state or 'Alta'} - {tool_condition or 'Bueno'}"
    if not status:
        status = material.status if material else "Alta - Bueno"
    status_change_reason = normalize_spaces(request.form.get("status_change_reason") or "")
    if material is None and _is_inactive_status(status) and not status_change_reason:
        return {}, "Debes capturar el motivo al crear un material en estado de baja."

    category = normalize_spaces(request.form.get("category") or "").upper()
    if category and category not in MATERIAL_CATEGORIES:
        return {}, "Selecciona una categoría válida."

    tutorial_url = normalize_spaces(request.form.get("tutorial_url") or "")
    image_url = normalize_spaces(request.form.get("image_url") or "")
    if tutorial_url and not (tutorial_url.startswith("http://") or tutorial_url.startswith("https://")):
        return {}, "La URL del tutorial debe iniciar con http:// o https://."
    if image_url and not (image_url.startswith("http://") or image_url.startswith("https://")):
        return {}, "La URL de imagen debe iniciar con http:// o https://."

    selected_location = normalize_spaces(request.form.get("location_choice") or "")
    if selected_location == NEW_LOCATION_SENTINEL:
        selected_location = request.form.get("location_new") or ""
    elif not selected_location:
        selected_location = request.form.get("location") or ""
    normalized_location = _normalize_location(selected_location)
    if not normalized_location:
        return {}, "Selecciona una ubicación existente o agrega una nueva."

    payload = {
        "lab_id": lab.id,
        "career_id": career.id,
        "name": name,
        "category": category or None,
        "location": normalized_location,
        "status": status,
        "pieces_text": normalize_spaces(request.form.get("pieces_text") or "") or (str(pieces_qty) if pieces_qty is not None else None),
        "pieces_qty": pieces_qty,
        "brand": normalize_spaces(request.form.get("brand") or "") or None,
        "model": normalize_spaces(request.form.get("model") or "") or None,
        "code": normalize_spaces(request.form.get("code") or "") or None,
        "serial": normalize_spaces(request.form.get("serial") or "") or None,
        "tutorial_url": tutorial_url or None,
        "image_url": image_url or None,
        "notes": normalize_spaces(request.form.get("notes") or "") or None,
    }
    if material is None and _is_inactive_status(status):
        payload["notes"] = status_change_reason
    return payload, None


def _status_change_reason_requirement(old_status: str | None, new_status: str | None) -> tuple[str | None, str | None]:
    old_is_inactive = _is_inactive_status(old_status)
    new_is_inactive = _is_inactive_status(new_status)
    if old_is_inactive == new_is_inactive:
        return None, None
    if not old_is_inactive and new_is_inactive:
        return "deactivation", "Motivo de baja"
    return "reactivation", "Motivo de reactivación"


def _status_form_defaults(material: Material | None, form_data: dict) -> tuple[str, str]:
    active_state = normalize_spaces(form_data.get("active_state") or "")
    tool_condition = normalize_spaces(form_data.get("tool_condition") or "")
    if active_state in {"Alta", "Baja"} and tool_condition in {"Bueno", "Regular", "Malo"}:
        return active_state, tool_condition
    source_status = form_data.get("status") or (material.status if material else None)
    return _split_tool_status(source_status)


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
    material_image_map = {m.id: _material_image_src(m) for m in materials}

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
        material_image_map=material_image_map,
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
    return render_template(
        "inventory/material_detail.html",
        material=m,
        material_image_src=_material_image_src(m),
        active_page="inventory",
    )


@inventory_bp.route("/admin/new", methods=["GET", "POST"])
@min_role_required("ADMIN")
def admin_new_material():
    default_lab = Lab.query.order_by(Lab.id.asc()).first()
    careers = Career.query.order_by(Career.name.asc()).all()
    form_data = {}

    if request.method == "POST":
        payload, error = _material_payload_from_form()
        form_data = dict(request.form)
        active_state_default, tool_condition_default = _status_form_defaults(None, form_data)
        image_ref, image_error = _save_material_image(request.files.get("image_file"))
        if not error and image_error:
            error = image_error
        if error:
            flash(error, "error")
            return render_template(
                "inventory/admin_form.html",
                material=None,
                default_lab_id=default_lab.id if default_lab else "",
                careers=careers,
                categories=MATERIAL_CATEGORIES,
                location_options=_existing_location_options([
                    form_data.get("location_choice"),
                    form_data.get("location_new"),
                    form_data.get("location"),
                ]),
                new_location_sentinel=NEW_LOCATION_SENTINEL,
                form_data=form_data,
                active_state_default=active_state_default,
                tool_condition_default=tool_condition_default,
                image_preview_src=None,
                active_page="inventory",
            )

        material = Material(**payload)
        if image_ref:
            material.image_ref = image_ref
            material.image_url = url_for("static", filename=image_ref)
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

    active_state_default, tool_condition_default = _status_form_defaults(None, form_data)
    return render_template(
        "inventory/admin_form.html",
        material=None,
        default_lab_id=default_lab.id if default_lab else "",
        careers=careers,
        categories=MATERIAL_CATEGORIES,
        location_options=_existing_location_options(),
        new_location_sentinel=NEW_LOCATION_SENTINEL,
        form_data=form_data,
        active_state_default=active_state_default,
        tool_condition_default=tool_condition_default,
        image_preview_src=None,
        active_page="inventory",
    )


@inventory_bp.route("/admin/<int:material_id>/edit", methods=["GET", "POST"])
@min_role_required("ADMIN")
def admin_edit_material(material_id: int):
    material = Material.query.get_or_404(material_id)
    careers = Career.query.order_by(Career.name.asc()).all()
    form_data = {}

    if request.method == "POST":
        payload, error = _material_payload_from_form(material)
        form_data = dict(request.form)
        active_state_default, tool_condition_default = _status_form_defaults(material, form_data)
        reason_value = normalize_spaces(request.form.get("status_change_reason") or "")
        remove_image = (request.form.get("remove_image") or "").strip() == "1"
        new_image_ref, image_error = _save_material_image(request.files.get("image_file"))
        if not error and image_error:
            error = image_error

        reason_type, reason_label = _status_change_reason_requirement(material.status, payload.get("status") if payload else None)
        if not error and reason_type and not reason_value:
            error = f"Debes indicar {reason_label.lower()}."

        if error:
            flash(error, "error")
            return render_template(
                "inventory/admin_form.html",
                material=material,
                default_lab_id=material.lab_id,
                careers=careers,
                categories=MATERIAL_CATEGORIES,
                location_options=_existing_location_options([
                    material.location,
                    form_data.get("location_choice"),
                    form_data.get("location_new"),
                    form_data.get("location"),
                ]),
                new_location_sentinel=NEW_LOCATION_SENTINEL,
                form_data=form_data,
                active_state_default=active_state_default,
                tool_condition_default=tool_condition_default,
                image_preview_src=_material_image_src(material),
                active_page="inventory",
            )

        old_status = material.status
        for key, value in payload.items():
            setattr(material, key, value)
        if remove_image:
            material.image_ref = None
            material.image_url = None
        if new_image_ref:
            material.image_ref = new_image_ref
            material.image_url = url_for("static", filename=new_image_ref)

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

    active_state_default, tool_condition_default = _status_form_defaults(material, form_data)
    return render_template(
        "inventory/admin_form.html",
        material=material,
        default_lab_id=material.lab_id,
        careers=careers,
        categories=MATERIAL_CATEGORIES,
        location_options=_existing_location_options([material.location]),
        new_location_sentinel=NEW_LOCATION_SENTINEL,
        form_data=form_data,
        active_state_default=active_state_default,
        tool_condition_default=tool_condition_default,
        image_preview_src=_material_image_src(material),
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
