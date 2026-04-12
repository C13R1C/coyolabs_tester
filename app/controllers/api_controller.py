from flask import Blueprint, current_app, jsonify, request
from flask_login import current_user

from app.extensions import db
from app.models.material import Material
from app.models.user import User
from app.services.audit_service import log_event
from app.services.debt_service import user_has_open_debts
from app.utils.media import resolve_media_url
from app.utils.roles import ROLE_STUDENT, normalize_role, role_at_least
from app.utils.security import api_key_required

api_bp = Blueprint("api", __name__, url_prefix="/api")


def _validate_ra_user(user: User | None) -> tuple[User | None, tuple[dict, int] | None]:
    if not user:
        return None, ({"error": "usuario no existe"}, 404)

    if not role_at_least(user.role, "STUDENT"):
        return None, ({"error": "rol no autorizado para RA"}, 403)

    if not user.is_active or user.is_banned:
        return None, ({"error": "usuario sin acceso activo"}, 403)

    if not user.is_verified:
        return None, ({"error": "usuario no verificado"}, 403)

    if user_has_open_debts(user.id):
        return None, ({"error": "usuario con adeudo activo, RA bloqueada"}, 403)

    return user, None


def _resolve_ra_user(raw_email: str | None) -> tuple[User | None, tuple[dict, int] | None]:
    if current_user.is_authenticated:
        if raw_email and raw_email.strip().lower() != (current_user.email or "").lower():
            return None, ({"error": "user_email no coincide con la sesion"}, 403)

        session_user = User.query.get(current_user.id)
        return _validate_ra_user(session_user)

    user_email = (raw_email or "").strip().lower()
    if not user_email:
        return None, ({"error": "user_email es requerido para esta operación"}, 400)

    user = User.query.filter_by(email=user_email).first()
    return _validate_ra_user(user)


def _can_user_access_ra_material(user: User, material: Material) -> tuple[bool, str | None]:
    # Reutiliza la misma regla aplicada en Solicitud de material:
    # el alumno sólo usa materiales de su propia carrera.
    if normalize_role(user.role) != ROLE_STUDENT:
        return True, None

    if material.career_id != user.career_id:
        return (
            False,
            "No tienes permitido usar este material porque no pertenece a tu carrera.",
        )

    return True, None


def material_to_dict(m: Material) -> dict:
    return {
        "id": m.id,
        "lab": m.lab.name if m.lab else None,
        "lab_id": m.lab_id,
        "name": m.name,
        "location": m.location,
        "status": m.status,
        "pieces_text": m.pieces_text,
        "pieces_qty": m.pieces_qty,
        "brand": m.brand,
        "model": m.model,
        "code": m.code,
        "serial": m.serial,
        "image_ref": m.image_ref,
        "tutorial_url": m.tutorial_url,
        "notes": m.notes,
    }


def ra_material_to_dict(m: Material) -> dict:
    career_name = m.career.name if m.career else None
    career_short = "".join(
        token[0] for token in (career_name or "").split() if token and token[0].isalnum()
    )[:6].upper() or None
    return {
        "id": m.id,
        "name": m.name,
        "career": career_name,
        "career_short": career_short,
        "location": m.location,
        "status": m.status,
        "pieces_text": m.pieces_text,
        "pieces_qty": m.pieces_qty,
        "tutorial_url": m.tutorial_url,
        "image_ref": m.image_ref,
        "image_url": resolve_media_url(m.image_ref, ensure_static_file=True),
        "notes": m.notes,
    }


@api_bp.route("/materials/<int:material_id>", methods=["GET"])
@api_key_required
def get_material(material_id: int):
    m = Material.query.get(material_id)
    if not m:
        return jsonify({"error": "Material no encontrado"}), 404
    return jsonify(material_to_dict(m)), 200


@api_bp.route("/materials", methods=["GET"])
@api_key_required
def search_materials():
    lab_id = request.args.get("lab_id", type=int)
    q = (request.args.get("q") or "").strip()

    query = Material.query
    if lab_id:
        query = query.filter(Material.lab_id == lab_id)

    if q:
        like = f"%{q}%"
        query = query.filter(
            (Material.name.ilike(like))
            | (Material.location.ilike(like))
            | (Material.code.ilike(like))
            | (Material.serial.ilike(like))
        )

    materials = query.order_by(Material.id.desc()).limit(200).all()
    return jsonify([material_to_dict(m) for m in materials]), 200


@api_bp.route("/ra/materials/<int:material_id>", methods=["GET"])
@api_key_required
def ra_get_material(material_id: int):
    user, resolve_error = _resolve_ra_user(request.args.get("user_email"))
    if resolve_error:
        payload, status = resolve_error
        return jsonify(payload), status

    current_app.logger.info("RA GET material %s by %s", material_id, user.email)

    m = Material.query.get(material_id)
    if not m:
        return jsonify({"error": "Material no encontrado"}), 404

    is_allowed, access_error = _can_user_access_ra_material(user, m)
    if not is_allowed:
        return jsonify({"error": access_error}), 403

    return jsonify({"ok": True, "material": ra_material_to_dict(m)}), 200


@api_bp.route("/ra/events", methods=["POST"])
@api_key_required
def ra_event():
    data = request.get_json(silent=True) or {}
    material_id = data.get("material_id")
    event_type = (data.get("event_type") or "").strip().lower()

    user, resolve_error = _resolve_ra_user(data.get("user_email"))
    if resolve_error:
        payload, status = resolve_error
        return jsonify(payload), status

    if event_type not in {"scan", "view", "open"}:
        return jsonify({"error": "event_type inválido. Usa: scan, view, open"}), 400

    if material_id is not None:
        m = Material.query.get(material_id)
        if not m:
            return jsonify({"error": "material_id no existe"}), 400
        is_allowed, access_error = _can_user_access_ra_material(user, m)
        if not is_allowed:
            return jsonify({"error": access_error}), 403

    current_app.logger.info("RA EVENT %s material %s", event_type, material_id)

    log_event(
        module="RA",
        action=f"RA_{event_type.upper()}",
        user_id=user.id,
        material_id=material_id,
        entity_label=f"Material #{material_id}" if material_id is not None else "RA event",
        description="Evento generado desde RA",
        metadata=None,
    )
    db.session.commit()

    return jsonify({"ok": True, "message": "Evento registrado"}), 200
