from datetime import datetime, timedelta

from flask import Blueprint, current_app, flash, jsonify, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import or_

from app.extensions import db
from app.models.notification import Notification
from app.models.user import User
from app.services.email_service import send_password_reset_email, send_verification_email
from app.services.notification_realtime_service import publish_notification_created
from app.services.token_service import (
    confirm_password_reset_token,
    confirm_verify_token,
    generate_password_reset_token,
    generate_verify_token,
    peek_verify_token,
)
from app.utils.landing import resolve_landing_endpoint
from app.utils.roles import ROLE_PENDING, ROLE_STUDENT, ROLE_TEACHER, infer_role_from_email, normalize_role
from app.utils.validators import is_valid_utpn_email


auth_bp = Blueprint("auth", __name__, url_prefix="/auth")
EMAIL_CHANGE_LIMIT_PER_HOUR = 3
EMAIL_VERIFY_TTL = timedelta(hours=1)


def _requires_profile_completion(role: str | None) -> bool:
    return normalize_role(role) in {ROLE_STUDENT, ROLE_TEACHER}


def _render_auth(mode: str = "login"):
    mode = (mode or "login").lower()
    if mode not in {"login", "register"}:
        mode = "login"
    return render_template(
        "auth/auth.html",
        mode=mode,
        pending_verify_email=session.get("pending_verify_email"),
    )


def _get_pending_verify_user() -> User | None:
    user_id = session.get("pending_verify_user_id")
    if not user_id:
        return None
    return User.query.get(user_id)


def _store_pending_verify_user(user: User) -> None:
    user_id = getattr(user, "id", None)
    email = getattr(user, "email", None)
    if not isinstance(user_id, int):
        return
    if not isinstance(email, str):
        return
    session["pending_verify_user_id"] = user_id
    session["pending_verify_email"] = email


def _bad_register_request(message: str):
    if request.is_json:
        return jsonify({"error": message}), 400

    flash(message, "error")
    return _render_auth("register"), 400


def _clear_pending_verify_session() -> None:
    session.pop("pending_verify_user_id", None)
    session.pop("pending_verify_email", None)


def _purge_users_with_dependencies(user_ids: list[int]) -> None:
    if not user_ids:
        return

    for table in db.metadata.sorted_tables:
        if table.name == "users":
            continue
        fk_columns = [
            column
            for column in table.c
            if any(fk.column.table.name == "users" and fk.column.name == "id" for fk in column.foreign_keys)
        ]
        if not fk_columns:
            continue
        db.session.execute(table.delete().where(or_(*[column.in_(user_ids) for column in fk_columns])))

    db.session.query(User).filter(User.id.in_(user_ids)).delete(synchronize_session=False)


def purge_expired_unverified_users(email: str | None = None) -> set[str]:
    now = datetime.utcnow()
    cutoff = now - EMAIL_VERIFY_TTL

    try:
        query = User.query.filter(
            User.is_verified.is_(False),
            User.verified_at.is_(None),
            User.created_at <= cutoff,
        )
        if email:
            normalized_email = email.strip().lower()
            query = query.filter(User.email == normalized_email)

        users = query.all()
    except Exception:
        return set()

    if not users:
        return set()

    user_ids = [u.id for u in users]
    purged_emails = {u.email for u in users if u.email}
    pending_id = session.get("pending_verify_user_id")
    pending_email = (session.get("pending_verify_email") or "").strip().lower()

    _purge_users_with_dependencies(user_ids)
    db.session.commit()

    if (isinstance(pending_id, int) and pending_id in user_ids) or (pending_email and pending_email in purged_emails):
        _clear_pending_verify_session()

    return purged_emails


def _is_accept_terms_valid(raw_value) -> bool:
    if isinstance(raw_value, bool):
        return raw_value
    if raw_value is None:
        return False
    return str(raw_value).strip().lower() in {"1", "true", "on", "yes"}


@auth_bp.route("/", methods=["GET"])
def auth_page():
    if current_user.is_authenticated:
        return redirect(url_for(resolve_landing_endpoint(current_user.role)))

    purge_expired_unverified_users()
    mode = request.args.get("mode", "login")
    return _render_auth(mode)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for(resolve_landing_endpoint(current_user.role)))

    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        purge_expired_unverified_users(email=email)

        user = User.query.filter_by(email=email).first()

        if not user or not user.check_password(password):
            flash("Credenciales incorrectas.", "error")
            return redirect(url_for("auth.auth_page", mode="login"))

        if not user.is_active:
            flash("Tu cuenta está desactivada. Contacta al administrador.", "warning")
            return redirect(url_for("auth.auth_page", mode="login"))

        if user.is_banned:
            flash("Tu cuenta está bloqueada. Contacta al administrador.", "warning")
            return redirect(url_for("auth.auth_page", mode="login"))

        if not user.is_verified:
            _store_pending_verify_user(user)
            flash("Verifica tu correo institucional para continuar.", "info")
            return redirect(url_for("auth.auth_page", mode="login"))

        if user.role == ROLE_PENDING:
            flash("Cuenta pendiente de aprobación por administrador.", "warning")
            return redirect(url_for("auth.auth_page", mode="login"))

        login_user(user)
        if _requires_profile_completion(user.role) and not user.profile_completed:
            return redirect(url_for("profile.complete_profile"))
        return redirect(url_for(resolve_landing_endpoint(user.role)))

    return redirect(url_for("auth.auth_page", mode="login"))


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for(resolve_landing_endpoint(current_user.role)))

    if request.method == "POST":
        data = (request.get_json(silent=True) or {}) if request.is_json else request.form

        email = (data.get("email") or "").strip().lower()
        password = data.get("password") or ""
        accept_terms = data.get("accept_terms")
        confirm_password = (
            data.get("confirm_password")
            or data.get("confirmPassword")
            or data.get("password_confirm")
            or ""
        )

        if not _is_accept_terms_valid(accept_terms):
            return _bad_register_request("Debes aceptar el Aviso de privacidad y los Términos y condiciones.")

        if not confirm_password:
            return _bad_register_request("confirm_password es obligatorio.")

        if password != confirm_password:
            return _bad_register_request("Las contraseñas no coinciden.")

        if not is_valid_utpn_email(email):
            return _bad_register_request("Solo se permiten correos institucionales (@utpn.edu.mx)")

        purge_expired_unverified_users(email=email)

        inferred_role = infer_role_from_email(email)
        if inferred_role is None:
            flash(
                "Formato de correo no válido. Usa matrícula@utpn.edu.mx o nombre.apellido@utpn.edu.mx.",
                "error",
            )
            return redirect(url_for("auth.auth_page", mode="register"))

        if len(password) < 6:
            flash("La contraseña debe tener al menos 6 caracteres.", "error")
            return redirect(url_for("auth.auth_page", mode="register"))

        existing = User.query.filter_by(email=email).first()
        if existing:
            flash(
                "Ese correo ya está registrado. Inicia sesión o usa recuperación de contraseña si olvidaste tu acceso.",
                "warning",
            )
            return redirect(url_for("auth.auth_page", mode="login"))

        user = User(email=email, role=inferred_role, is_verified=False)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        notifications_created: list[Notification] = []
        if inferred_role == ROLE_PENDING:
            admins = User.query.filter(User.role.in_(["ADMIN", "SUPERADMIN"])).all()
            for admin in admins:
                notif = Notification(
                    user_id=admin.id,
                    title="Perfil pendiente por resolver",
                    message=f"Nueva cuenta pendiente: {user.email}. Asigna rol desde Administrar perfiles y roles.",
                    link=url_for("users.create_admin_account"),
                    event_code="PENDING_PROFILE",
                    is_persistent=True,
                    related_user_id=user.id,
                )
                db.session.add(notif)
                notifications_created.append(notif)
            db.session.commit()
            for notif in notifications_created:
                publish_notification_created(notif)

        token = generate_verify_token(email, user.verify_token_version or 0)
        base_url = current_app.config.get("APP_BASE_URL", "http://127.0.0.1:5000")
        verify_link = f"{base_url}/auth/verify/{token}"

        try:
            result = send_verification_email(email, verify_link)
            print("=== EMAIL ENVIADO CON RESEND ===")
            print(result)
            print("=== FIN EMAIL ===")
        except Exception as e:
            print("=== ERROR ENVIANDO EMAIL CON RESEND ===")
            print(e)
            print("=== FIN ERROR EMAIL ===")
            flash("La cuenta se creó, pero no se pudo enviar el correo de verificación.", "warning")
            return redirect(url_for("auth.auth_page", mode="login"))

        _store_pending_verify_user(user)
        flash("Te registraste correctamente. Verifica tu correo institucional para activar la cuenta.", "success")
        return redirect(url_for("auth.auth_page", mode="login"))

    return redirect(url_for("auth.auth_page", mode="register"))


@auth_bp.route("/verify/<token>", methods=["GET"])
def verify(token):
    purge_expired_unverified_users()
    token_data = confirm_verify_token(token, max_age_seconds=3600)
    if not token_data:
        token_preview = peek_verify_token(token)
        token_email = str((token_preview or {}).get("email") or "").strip().lower()
        if token_email:
            purged_emails = purge_expired_unverified_users(email=token_email)
            if token_email in purged_emails:
                flash("Tu registro expiró por no verificar el correo a tiempo. Debes registrarte nuevamente.", "warning")
                return redirect(url_for("auth.auth_page", mode="register"))
        flash("Token inválido o expirado.", "error")
        return redirect(url_for("auth.auth_page", mode="login"))

    email = str(token_data.get("email") or "").strip().lower()
    token_version = int(token_data.get("token_version") or 0)

    purged_emails = purge_expired_unverified_users(email=email)
    if email in purged_emails:
        flash("Tu registro expiró por no verificar el correo a tiempo. Debes registrarte nuevamente.", "warning")
        return redirect(url_for("auth.auth_page", mode="register"))

    user = User.query.filter_by(email=email).first()
    if not user:
        flash("Tu registro expiró por no verificar el correo a tiempo. Debes registrarte nuevamente.", "warning")
        return redirect(url_for("auth.auth_page", mode="register"))
    if token_version != (user.verify_token_version or 0):
        flash("Token inválido o expirado.", "error")
        return redirect(url_for("auth.auth_page", mode="login"))

    if user.is_verified:
        flash("Correo ya verificado. Bienvenido.", "success")
        login_user(user)
        if _requires_profile_completion(user.role) and not user.profile_completed:
            return redirect(url_for("profile.complete_profile"))
        return redirect(url_for(resolve_landing_endpoint(user.role)))

    user.is_verified = True
    user.verified_at = db.func.now()
    user.email_change_count = 0
    user.email_change_window_started_at = None
    db.session.commit()

    _clear_pending_verify_session()
    flash("Correo verificado correctamente.", "success")
    login_user(user)
    if _requires_profile_completion(user.role) and not user.profile_completed:
        return redirect(url_for("profile.complete_profile"))
    return redirect(url_for(resolve_landing_endpoint(user.role)))


@auth_bp.route("/change-email", methods=["POST"])
def change_email():
    user = _get_pending_verify_user()
    if not user:
        return jsonify({"error": "No hay una cuenta pendiente de verificación en esta sesión."}), 401

    if user.is_verified:
        return jsonify({"error": "La cuenta ya está verificada. No es necesario cambiar correo."}), 400

    now = datetime.utcnow()
    window_start = user.email_change_window_started_at
    if not window_start or (now - window_start) >= timedelta(hours=1):
        user.email_change_window_started_at = now
        user.email_change_count = 0

    if (user.email_change_count or 0) >= EMAIL_CHANGE_LIMIT_PER_HOUR:
        return jsonify({"error": "Límite alcanzado: máximo 3 cambios de correo por hora."}), 429

    data = (request.get_json(silent=True) or {}) if request.is_json else request.form
    new_email = (data.get("email") or "").strip().lower()
    if not new_email:
        return jsonify({"error": "El correo es obligatorio."}), 400
    if not is_valid_utpn_email(new_email):
        return jsonify({"error": "Solo se permiten correos institucionales (@utpn.edu.mx)"}), 400

    inferred_role = infer_role_from_email(new_email)
    if inferred_role is None:
        return jsonify(
            {"error": "Formato de correo no válido. Usa matrícula@utpn.edu.mx o nombre.apellido@utpn.edu.mx."}
        ), 400

    existing = User.query.filter(User.email == new_email, User.id != user.id).first()
    if existing:
        return jsonify({"error": "Ese correo ya está registrado en otra cuenta."}), 409

    user.email = new_email
    user.role = inferred_role
    user.is_verified = False
    user.verified_at = None
    user.verify_token_version = (user.verify_token_version or 0) + 1
    user.email_change_count = (user.email_change_count or 0) + 1

    token = generate_verify_token(user.email, user.verify_token_version)
    base_url = current_app.config.get("APP_BASE_URL", "http://127.0.0.1:5000")
    verify_link = f"{base_url}/auth/verify/{token}"

    try:
        result = send_verification_email(user.email, verify_link)
        print("=== EMAIL REENVIADO CON RESEND ===")
        print(result)
        print("=== FIN EMAIL ===")
    except Exception as e:
        print("=== ERROR REENVIANDO EMAIL CON RESEND ===")
        print(e)
        print("=== FIN ERROR EMAIL ===")
        return jsonify({"error": "No se pudo reenviar el correo de verificación."}), 500

    db.session.commit()

    _store_pending_verify_user(user)
    return jsonify({"message": "Correo actualizado y verificación reenviada."}), 200


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.auth_page", mode="login"))


@auth_bp.route("/forgot-password", methods=["POST"])
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for(resolve_landing_endpoint(current_user.role)))

    email = (request.form.get("email") or "").strip().lower()
    generic_message = "Si el correo está registrado, enviaremos un enlace de recuperación."

    user = User.query.filter_by(email=email).first() if email else None
    if user and user.is_active and not user.is_banned:
        token = generate_password_reset_token(user.email, user.password_hash)
        base_url = current_app.config.get("APP_BASE_URL", "http://127.0.0.1:5000")
        reset_link = f"{base_url}/auth/reset-password/{token}"
        try:
            send_password_reset_email(user.email, reset_link)
        except Exception as e:
            print("=== ERROR ENVIANDO EMAIL RESET PASSWORD ===")
            print(e)
            print("=== FIN ERROR EMAIL RESET PASSWORD ===")

    flash(generic_message, "info")
    return redirect(url_for("auth.auth_page", mode="login"))


@auth_bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token: str):
    token_data = confirm_password_reset_token(token, max_age_seconds=3600)
    if not token_data:
        flash("El enlace de recuperación es inválido o expiró.", "error")
        return redirect(url_for("auth.auth_page", mode="login"))

    email = str(token_data.get("email") or "").strip().lower()
    password_fingerprint = str(token_data.get("password_fingerprint") or "")
    user = User.query.filter_by(email=email).first()
    if not user or not user.is_active or user.is_banned:
        flash("El enlace de recuperación es inválido o expiró.", "error")
        return redirect(url_for("auth.auth_page", mode="login"))

    if password_fingerprint != user.password_hash:
        flash("El enlace de recuperación es inválido o expiró.", "error")
        return redirect(url_for("auth.auth_page", mode="login"))

    if request.method == "POST":
        password = request.form.get("password") or ""
        confirm_password = request.form.get("confirm_password") or ""

        if not password or not confirm_password:
            flash("Debes completar ambos campos.", "warning")
            return redirect(url_for("auth.reset_password", token=token))

        if password != confirm_password:
            flash("Las contraseñas no coinciden.", "error")
            return redirect(url_for("auth.reset_password", token=token))

        if len(password) < 6:
            flash("La contraseña debe tener al menos 6 caracteres.", "error")
            return redirect(url_for("auth.reset_password", token=token))

        if user.check_password(password):
            flash("La nueva contraseña debe ser distinta a la actual.", "warning")
            return redirect(url_for("auth.reset_password", token=token))

        user.set_password(password)
        db.session.commit()
        flash("Tu contraseña se actualizó correctamente. Ya puedes iniciar sesión.", "success")
        return redirect(url_for("auth.auth_page", mode="login"))

    return render_template("auth/reset_password.html", token=token)


@auth_bp.route("/me", methods=["GET"])
@login_required
def me():
    return {
        "id": current_user.id,
        "email": current_user.email,
        "role": current_user.role,
        "is_verified": current_user.is_verified,
    }
