import re

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import func
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.models.academic_level import AcademicLevel
from app.models.career import Career
from app.models.debt import Debt
from app.models.inventory_request_ticket import InventoryRequestTicket
from app.models.notification import Notification
from app.models.profile_change_request import ProfileChangeRequest
from app.models.reservation import Reservation
from app.models.subject import Subject
from app.models.teacher_academic_load import TeacherAcademicLoad
from app.models.user import User
from app.services.audit_service import log_event
from app.utils.landing import resolve_landing_endpoint
from app.utils.validators import normalize_and_validate_group_code, normalize_and_validate_phone
from app.utils.roles import ROLE_TEACHER, ROLE_STUDENT, is_admin_role, normalize_role

profile_bp = Blueprint("profile", __name__, url_prefix="/profile")

ALLOWED_CAREER_LEVEL_CODES: dict[str, tuple[str, ...]] = {
    "ING. EN MECATRÓNICA": ("TSU", "ING"),
    "ING INDUSTRIAL": ("TSU", "ING"),
    "ING. EN LOGÍSTICA INTERNACIONAL": ("TSU", "ING"),
    "ING. EN TECNOLOGÍAS DE LA INFORMACIÓN E INNOVACIÓN DIGITAL": ("TSU", "ING"),
    "LIC. EN ARQUITECTURA": ("TSU", "LIC"),
    "LIC. EN ADMINISTRACIÓN": ("TSU", "LIC"),
    "LIC EN CONTADURÍA": ("TSU", "LIC"),
}


def _build_profile_catalog_options() -> tuple[list[Career], list[AcademicLevel], dict[int, list[int]]]:
    careers = Career.query.filter(Career.name.in_(tuple(ALLOWED_CAREER_LEVEL_CODES.keys()))).all()
    careers_by_name = {career.name: career for career in careers}
    ordered_careers = [
        careers_by_name[name]
        for name in ALLOWED_CAREER_LEVEL_CODES.keys()
        if name in careers_by_name
    ]

    academic_levels = (
        AcademicLevel.query
        .filter(
            AcademicLevel.is_active.is_(True),
            func.upper(AcademicLevel.code).in_(("TSU", "ING", "LIC")),
        )
        .all()
    )
    levels_by_code = {level.code.upper(): level for level in academic_levels}
    ordered_level_codes = ("TSU", "ING", "LIC")
    ordered_levels = [levels_by_code[code] for code in ordered_level_codes if code in levels_by_code]

    career_level_map: dict[int, list[int]] = {}
    for career in ordered_careers:
        allowed_codes = ALLOWED_CAREER_LEVEL_CODES.get(career.name, ())
        allowed_level_ids = [
            levels_by_code[code].id
            for code in allowed_codes
            if code in levels_by_code
        ]
        career_level_map[career.id] = allowed_level_ids

    return ordered_careers, ordered_levels, career_level_map


def _is_professor_role(role: str | None) -> bool:
    normalized = normalize_role(role)
    return normalized == ROLE_TEACHER


def _requires_profile_completion(role: str | None) -> bool:
    normalized = normalize_role(role)
    return normalized in {ROLE_STUDENT, ROLE_TEACHER}


def _has_min_real_chars(value: str, minimum: int = 3) -> bool:
    normalized = re.sub(r"\s+", "", value or "")
    return len(normalized) >= minimum


def _normalize_group_name(raw_group_name: str | None) -> tuple[str | None, str | None]:
    group_name = (raw_group_name or "").strip()
    if not group_name:
        return None, None
    if len(group_name) > 80:
        return None, "El grupo no puede exceder 80 caracteres."
    return group_name, None


def _normalize_and_validate_matricula(raw_matricula: str | None, role: str | None, email: str | None) -> tuple[str | None, str | None]:
    normalized_role = normalize_role(role)
    if normalized_role != ROLE_STUDENT:
        return (email or "").strip().lower(), None

    matricula = re.sub(r"\s+", "", raw_matricula or "")
    if not matricula:
        return None, "La matrícula es obligatoria."
    if not matricula.isdigit():
        return None, "La matrícula debe contener solo números."
    if len(matricula) != 8:
        return None, "La matrícula debe tener exactamente 8 dígitos."
    return matricula, None


def _subject_allowed_for_teacher(subject: Subject, teacher: User) -> bool:
    if not subject or not teacher:
        return False

    if teacher.career_id and subject.career_id != teacher.career_id:
        return False

    teacher_level = (teacher.academic_level or "").strip().upper()
    subject_level = (subject.level or "").strip().upper()
    if teacher_level and subject_level and teacher_level != subject_level:
        return False

    return True


@profile_bp.route("/", methods=["GET"])
@login_required
def my_profile():
    reservations = (
        Reservation.query
        .filter(Reservation.user_id == current_user.id)
        .order_by(Reservation.created_at.desc())
        .all()
    )

    material_requests = (
        InventoryRequestTicket.query
        .filter(InventoryRequestTicket.user_id == current_user.id)
        .order_by(InventoryRequestTicket.request_date.desc(), InventoryRequestTicket.created_at.desc())
        .all()
    )

    debts = (
        Debt.query
        .options(joinedload(Debt.material))
        .filter(Debt.user_id == current_user.id)
        .order_by(Debt.created_at.desc())
        .all()
    )

    available_subjects = []
    teacher_loads = []
    catalog_filters = {"q": "", "career_id": "", "level": ""}
    catalog_careers = []
    catalog_levels = []
    teacher_scope = {"career": None, "level": None}
    if _is_professor_role(current_user.role):
        q = (request.args.get("q") or "").strip()
        selected_career_id = request.args.get("career_id", type=int)
        selected_level = (request.args.get("level") or "").strip().upper()

        catalog_filters = {
            "q": q,
            "career_id": str(selected_career_id or ""),
            "level": selected_level,
        }

        teacher_loads = (
            TeacherAcademicLoad.query
            .options(joinedload(TeacherAcademicLoad.subject).joinedload(Subject.career))
            .filter(TeacherAcademicLoad.teacher_id == current_user.id)
            .order_by(TeacherAcademicLoad.group_code.asc())
            .all()
        )
        teacher_scope = {
            "career": current_user.career_rel.name if current_user.career_rel else (current_user.career or None),
            "level": current_user.academic_level,
        }
        catalog_q = (
            Subject.query
            .options(joinedload(Subject.career), joinedload(Subject.academic_level))
            .filter(Subject.is_active.is_(True))
        )
        if q:
            like = f"%{q.lower()}%"
            catalog_q = catalog_q.filter(func.lower(Subject.name).like(like))
        if selected_career_id:
            catalog_q = catalog_q.filter(Subject.career_id == selected_career_id)
        if selected_level:
            catalog_q = catalog_q.filter(func.upper(Subject.level) == selected_level)
        if current_user.career_id:
            catalog_q = catalog_q.filter(Subject.career_id == current_user.career_id)
        if current_user.academic_level:
            catalog_q = catalog_q.filter(func.upper(Subject.level) == current_user.academic_level.upper())

        available_subjects = (
            catalog_q
            .order_by(Subject.name.asc(), Subject.level.asc(), Subject.quarter.asc())
            .all()
        )
        catalog_careers = Career.query.order_by(Career.name.asc()).all()
        catalog_levels = (
            db.session.query(func.upper(Subject.level))
            .filter(Subject.is_active.is_(True), Subject.level.isnot(None))
            .distinct()
            .order_by(func.upper(Subject.level))
            .all()
        )
        catalog_levels = [row[0] for row in catalog_levels if row and row[0]]

    return render_template(
        "profile/my_profile.html",
        reservations=reservations,
        material_requests=material_requests,
        debts=debts,
        active_page="profile",
        is_professor=_is_professor_role(current_user.role),
        teacher_loads=teacher_loads,
        available_subjects=available_subjects,
        catalog_filters=catalog_filters,
        catalog_careers=catalog_careers,
        catalog_levels=catalog_levels,
        teacher_scope=teacher_scope,
    )


@profile_bp.route("/teaching-load/add", methods=["POST"])
@login_required
def add_teaching_load():
    if not _is_professor_role(current_user.role):
        flash("Solo profesores pueden gestionar carga académica.", "error")
        return redirect(url_for("profile.my_profile"))

    subject_id = request.form.get("subject_id", type=int)
    group_code, group_error = normalize_and_validate_group_code(request.form.get("group_code"))

    if not subject_id:
        flash("La materia es obligatoria.", "error")
        return redirect(url_for("profile.my_profile"))

    if group_error:
        flash(group_error, "error")
        return redirect(url_for("profile.my_profile"))

    subject = Subject.query.get(subject_id)
    if not subject:
        flash("Materia no encontrada.", "error")
        return redirect(url_for("profile.my_profile"))
    if not subject.is_active:
        flash("La materia seleccionada está inactiva.", "error")
        return redirect(url_for("profile.my_profile"))
    if not _subject_allowed_for_teacher(subject, current_user):
        flash("No puedes asignar materias fuera de tu carrera o nivel académico.", "error")
        return redirect(url_for("profile.my_profile"))

    existing = TeacherAcademicLoad.query.filter_by(
        teacher_id=current_user.id,
        subject_id=subject_id,
        group_code=group_code,
    ).first()
    if existing:
        flash("Esa asignación ya existe.", "warning")
        return redirect(url_for("profile.my_profile"))

    load = TeacherAcademicLoad(
        teacher_id=current_user.id,
        subject_id=subject_id,
        group_code=group_code,
    )
    db.session.add(load)
    db.session.commit()
    log_event(
        module="PROFILE",
        action="TEACHING_LOAD_ADDED",
        user_id=current_user.id,
        entity_label=f"TeacherLoad #{load.id}",
        description=f"Carga agregada: {subject.name} · grupo {group_code}",
        metadata={"load_id": load.id, "subject_id": subject.id, "group_code": group_code},
    )
    db.session.commit()

    flash("Carga académica agregada.", "success")
    return redirect(url_for("profile.my_profile"))


@profile_bp.route("/teaching-load/<int:load_id>/remove", methods=["POST"])
@login_required
def remove_teaching_load(load_id: int):
    if not _is_professor_role(current_user.role):
        flash("Solo profesores pueden gestionar carga académica.", "error")
        return redirect(url_for("profile.my_profile"))

    load = TeacherAcademicLoad.query.get_or_404(load_id)
    if load.teacher_id != current_user.id:
        flash("No autorizado.", "error")
        return redirect(url_for("profile.my_profile"))

    subject_name = load.subject.name if load.subject else f"Materia #{load.subject_id}"
    group_code = load.group_code

    db.session.delete(load)
    db.session.commit()
    log_event(
        module="PROFILE",
        action="TEACHING_LOAD_REMOVED",
        user_id=current_user.id,
        entity_label=f"TeacherLoad #{load_id}",
        description=f"Carga eliminada: {subject_name} · grupo {group_code}",
        metadata={"load_id": load_id, "subject_id": load.subject_id, "group_code": group_code},
    )
    db.session.commit()

    flash("Asignación eliminada.", "success")
    return redirect(url_for("profile.my_profile"))


@profile_bp.route("/request-update", methods=["POST"])
@login_required
def request_profile_update():
    legacy_phone = (request.form.get("requested_phone") or "").strip()
    if legacy_phone:
        flash("Redirigiendo al flujo principal de cambio de teléfono.", "info")
        return request_phone_change()

    if is_admin_role(current_user.role):
        flash("Tu cuenta administrativa no requiere solicitud de actualización de perfil.", "info")
        return redirect(url_for("profile.my_profile"))

    pending = (
        ProfileChangeRequest.query
        .filter(ProfileChangeRequest.user_id == current_user.id)
        .filter(ProfileChangeRequest.request_type == "PROFILE_CHANGE")
        .filter(ProfileChangeRequest.status == "PENDING")
        .first()
    )
    if pending:
        flash("Ya tienes una solicitud de actualización de perfil pendiente.", "warning")
        return redirect(url_for("profile.my_profile"))

    req = ProfileChangeRequest(
        user_id=current_user.id,
        request_type="PROFILE_CHANGE",
        reason="Solicitud recibida desde el formulario de actualización de perfil",
        status="PENDING",
    )
    db.session.add(req)

    admins = User.query.filter(User.role.in_(["ADMIN", "SUPERADMIN"])).all()
    for admin in admins:
        notif = Notification(
            user_id=admin.id,
            title="Solicitud de actualización de perfil",
            message=f"{current_user.email} generó una solicitud de perfil (canal unificado).",
            link=url_for("users.profile_change_requests"),
        )
        db.session.add(notif)

    db.session.commit()
    log_event(
        module="PROFILE",
        action="PROFILE_UPDATE_REQUEST_USED",
        user_id=current_user.id,
        entity_label="/profile/request-update",
        description="Uso de formulario de actualización de perfil",
        metadata={"preferred_flows": ["/profile/phone-change/request", "/profile/complete"]},
    )
    flash("Solicitud registrada correctamente.", "success")
    return redirect(url_for("profile.my_profile"))


@profile_bp.route("/phone-change/request", methods=["POST"])
@login_required
def request_phone_change():
    if _is_professor_role(current_user.role):
        flash("Como profesor puedes editar tu teléfono directamente.", "info")
        return redirect(url_for("profile.my_profile"))

    phone_raw = request.form.get("requested_phone")
    reason = (request.form.get("reason") or "").strip()

    phone, phone_error = normalize_and_validate_phone(phone_raw)
    if phone_error:
        flash(phone_error, "error")
        return redirect(url_for("profile.my_profile"))

    pending = (
        ProfileChangeRequest.query
        .filter(ProfileChangeRequest.user_id == current_user.id)
        .filter(ProfileChangeRequest.request_type == "PHONE_CHANGE")
        .filter(ProfileChangeRequest.status == "PENDING")
        .first()
    )
    if pending:
        flash("Ya tienes una solicitud de cambio de teléfono pendiente.", "warning")
        return redirect(url_for("profile.my_profile"))

    req = ProfileChangeRequest(
        user_id=current_user.id,
        request_type="PHONE_CHANGE",
        requested_phone=phone,
        reason=reason or None,
        status="PENDING",
    )
    db.session.add(req)

    admins = User.query.filter(User.role.in_(["ADMIN", "SUPERADMIN"])).all()
    for admin in admins:
        notif = Notification(
            user_id=admin.id,
            title="Solicitud de cambio de teléfono",
            message=f"{current_user.email} solicitó actualización de teléfono.",
            link=url_for("users.profile_change_requests"),
        )
        db.session.add(notif)

    db.session.commit()
    log_event(
        module="PROFILE",
        action="PHONE_CHANGE_REQUESTED",
        user_id=current_user.id,
        entity_label=f"ProfileChangeRequest #{req.id}",
        description="Solicitud de cambio de teléfono enviada",
        metadata={"request_id": req.id, "requested_phone": phone},
    )
    db.session.commit()
    flash("Solicitud de cambio de teléfono enviada.", "success")
    return redirect(url_for("profile.my_profile"))


@profile_bp.route("/phone/update", methods=["POST"])
@login_required
def update_phone():
    if not _is_professor_role(current_user.role):
        flash("Solo profesores pueden editar teléfono directamente.", "error")
        return redirect(url_for("profile.my_profile"))

    phone, phone_error = normalize_and_validate_phone(request.form.get("phone"))
    if phone_error:
        flash(phone_error, "error")
        return redirect(url_for("profile.my_profile"))

    old_phone = current_user.phone
    current_user.phone = phone
    db.session.commit()
    log_event(
        module="PROFILE",
        action="PHONE_UPDATED_DIRECT",
        user_id=current_user.id,
        entity_label=f"User #{current_user.id}",
        description="Teléfono actualizado directamente por profesor",
        metadata={"old_phone": old_phone, "new_phone": phone},
    )
    db.session.commit()
    flash("Teléfono actualizado.", "success")
    return redirect(url_for("profile.my_profile"))


@profile_bp.route("/password/change", methods=["POST"])
@login_required
def change_password():
    current_password = request.form.get("current_password") or ""
    new_password = request.form.get("new_password") or ""
    confirm_new_password = request.form.get("confirm_new_password") or ""

    if not current_password or not new_password or not confirm_new_password:
        flash("Completa todos los campos para cambiar tu contraseña.", "error")
        return redirect(url_for("profile.my_profile"))

    if not current_user.check_password(current_password):
        flash("La contraseña actual es incorrecta.", "error")
        return redirect(url_for("profile.my_profile"))

    if new_password != confirm_new_password:
        flash("La nueva contraseña y su confirmación no coinciden.", "error")
        return redirect(url_for("profile.my_profile"))

    if current_password == new_password:
        flash("La nueva contraseña debe ser distinta a la actual.", "error")
        return redirect(url_for("profile.my_profile"))

    if len(new_password) < 6:
        flash("La nueva contraseña debe tener al menos 6 caracteres.", "error")
        return redirect(url_for("profile.my_profile"))

    current_user.set_password(new_password)
    db.session.commit()
    log_event(
        module="PROFILE",
        action="PASSWORD_CHANGED",
        user_id=current_user.id,
        entity_label=f"User #{current_user.id}",
        description="Cambio de contraseña realizado por el usuario",
        metadata={"self_service": True},
    )
    db.session.commit()
    flash("Contraseña actualizada correctamente.", "success")
    return redirect(url_for("profile.my_profile"))


@profile_bp.route("/group/update", methods=["POST"])
@login_required
def update_group_name():
    if normalize_role(current_user.role) != ROLE_STUDENT:
        flash("Solo estudiantes pueden actualizar su grupo desde este formulario.", "error")
        return redirect(url_for("profile.my_profile"))

    group_name, group_error = _normalize_group_name(request.form.get("group_name"))
    if group_error:
        flash(group_error, "error")
        return redirect(url_for("profile.my_profile"))

    old_group_name = (current_user.group_name or "").strip() or None
    if old_group_name == group_name:
        flash("No detectamos cambios en tu grupo.", "info")
        return redirect(url_for("profile.my_profile"))

    current_user.group_name = group_name
    db.session.commit()
    log_event(
        module="PROFILE",
        action="GROUP_NAME_UPDATED",
        user_id=current_user.id,
        entity_label=f"User #{current_user.id}",
        description="Grupo actualizado por el estudiante desde Mi perfil",
        metadata={"old_group_name": old_group_name, "new_group_name": group_name},
    )
    db.session.commit()
    flash("Tu grupo se actualizó correctamente.", "success")
    return redirect(url_for("profile.my_profile"))


@profile_bp.route("/update-basic", methods=["POST"])
@login_required
def update_basic_profile():
    normalized_role = normalize_role(current_user.role)
    if normalized_role not in {"ADMIN", "SUPERADMIN"}:
        flash("Solo cuentas ADMIN/SUPERADMIN pueden editar estos datos directamente.", "error")
        return redirect(url_for("profile.my_profile"))

    full_name = (request.form.get("full_name")or"").strip()
    phone, phone_error = normalize_and_validate_phone(request.form.get("phone"))

    if not full_name or not _has_min_real_chars(full_name, minimum=3):
        flash("El nombre completo es obligatorio y debe tener al menos 3 caracteres reales.", "error")
        return redirect(url_for("profile.my_profile"))

    if phone_error:
        flash(phone_error, "error")
        return redirect(url_for("profile.my_profile"))

    blocked_attempts = []
    restricted_fields = {
        "matricula": current_user.matricula or "",
        "career": current_user.career or "",
        "academic_level": current_user.academic_level or "",
    }
    for field_name, current_value in restricted_fields.items():
        submitted_value = (request.form.get(field_name) or "").strip()
        if submitted_value and submitted_value != str(current_value):
            blocked_attempts.append(field_name)

    changed_fields = []
    if full_name != (current_user.full_name or ""):
        changed_fields.append("full_name")
    if phone != (current_user.phone or ""):
        changed_fields.append("phone")

    current_user.full_name = full_name
    current_user.phone = phone
    db.session.commit()

    log_event(
        module="PROFILE",
        action="PROFILE_UPDATED",
        user_id=current_user.id,
        entity_label=f"User #{current_user.id}",
        description="Actualización de perfil por el usuario",
        metadata={
            "changed_fields": changed_fields,
            "blocked_fields_attempted": blocked_attempts,
        },
    )
    db.session.commit()

    if blocked_attempts:
        flash("Se guardaron tus cambios permitidos. Los datos académicos solo pueden modificarse por administración.", "warning")
        return redirect(url_for("profile.my_profile"))

    if not changed_fields:
        flash("No detectamos cambios en tu perfil.", "info")
        return redirect(url_for("profile.my_profile"))

    flash("Tu perfil se actualizó correctamente.", "success")
    return redirect(url_for("profile.my_profile"))


@profile_bp.route("/complete", methods=["GET", "POST"])
@login_required
def complete_profile():
    if not _requires_profile_completion(current_user.role):
        if not current_user.profile_completed:
            current_user.profile_completed = True
            current_user.profile_data_confirmed = True
            current_user.profile_confirmed_at = db.func.now()
            db.session.commit()
        return redirect(url_for(resolve_landing_endpoint(current_user.role)))

    if current_user.profile_completed:
        flash("Tu perfil ya está completo.")
        return redirect(url_for(resolve_landing_endpoint(current_user.role)))

    is_professor = _is_professor_role(current_user.role)
    is_student = normalize_role(current_user.role) == ROLE_STUDENT

    if request.method == "POST":
        full_name = (request.form.get("full_name") or "").strip()
        matricula_raw = request.form.get("matricula")
        career_id = request.form.get("career_id", type=int)
        academic_level_id = request.form.get("academic_level_id", type=int)
        phone = (request.form.get("phone") or "").strip()
        group_name_raw = request.form.get("group_name")
        confirm_data = request.form.get("confirm_data") == "1"

        if not full_name or not _has_min_real_chars(full_name, minimum=3):
            flash("El nombre completo es obligatorio y debe tener al menos 3 caracteres reales.")
            return redirect(url_for("profile.complete_profile"))

        matricula, matricula_error = _normalize_and_validate_matricula(
            matricula_raw,
            current_user.role,
            current_user.email,
        )
        if matricula_error:
            flash(matricula_error)
            return redirect(url_for("profile.complete_profile"))

        if not career_id:
            flash("La carrera es obligatoria.")
            return redirect(url_for("profile.complete_profile"))

        if not phone:
            flash("El teléfono es obligatorio.")
            return redirect(url_for("profile.complete_profile"))

        group_name, group_name_error = _normalize_group_name(group_name_raw)
        if group_name_error:
            flash(group_name_error)
            return redirect(url_for("profile.complete_profile"))

        if not confirm_data:
            flash("Debes confirmar que tus datos son correctos para continuar.")
            return redirect(url_for("profile.complete_profile"))

        _, _, career_level_map = _build_profile_catalog_options()

        career_obj = Career.query.get(career_id)
        if not career_obj:
            flash("La carrera seleccionada no existe.")
            return redirect(url_for("profile.complete_profile"))

        if career_obj.name not in ALLOWED_CAREER_LEVEL_CODES:
            flash("La carrera seleccionada no está habilitada para este formulario.")
            return redirect(url_for("profile.complete_profile"))

        if is_student and not academic_level_id:
            flash("El nivel académico es obligatorio para estudiantes.")
            return redirect(url_for("profile.complete_profile"))

        level_obj = AcademicLevel.query.get(academic_level_id) if academic_level_id else None

        if academic_level_id and not level_obj:
            flash("El nivel académico seleccionado no existe.")
            return redirect(url_for("profile.complete_profile"))

        if level_obj and level_obj.code.upper() not in {"TSU", "ING", "LIC"}:
            flash("El nivel académico seleccionado no está habilitado.")
            return redirect(url_for("profile.complete_profile"))

        if is_student and level_obj:
            allowed_level_ids = set(career_level_map.get(career_obj.id, []))
            if level_obj.id not in allowed_level_ids:
                flash("La combinación de carrera y nivel no es válida.")
                return redirect(url_for("profile.complete_profile"))

        current_user.full_name = full_name
        current_user.career_id = career_obj.id
        current_user.career = career_obj.name
        current_user.career_year = None
        current_user.phone = phone

        if is_student:
            current_user.matricula = matricula
            current_user.academic_level_id = level_obj.id if level_obj else None
            current_user.academic_level = level_obj.code if level_obj else None
            current_user.group_name = group_name
            current_user.professor_subjects = None
        else:
            current_user.matricula = None
            current_user.academic_level_id = level_obj.id if level_obj else None
            current_user.academic_level = level_obj.code if level_obj else None
            current_user.group_name = None

        current_user.profile_completed = True
        current_user.profile_data_confirmed = True
        current_user.profile_confirmed_at = db.func.now()

        db.session.commit()
        log_event(
            module="PROFILE",
            action="PROFILE_COMPLETED",
            user_id=current_user.id,
            entity_label=f"User #{current_user.id}",
            description="Perfil completado por el usuario",
            metadata={
                "career_id": career_obj.id,
                "academic_level_id": level_obj.id if level_obj else None,
                "role": current_user.role,
                "profile_identifier": matricula,
            },
        )
        db.session.commit()

        flash("Perfil completado correctamente.")
        return redirect(url_for(resolve_landing_endpoint(current_user.role)))

    careers, academic_levels, career_level_map = _build_profile_catalog_options()
    return render_template(
        "profile/complete.html",
        is_professor=is_professor,
        is_student=is_student,
        careers=careers,
        academic_levels=academic_levels,
        career_level_map=career_level_map,
    )
