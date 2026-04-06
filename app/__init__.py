#app init
import secrets

from flask import Flask, redirect, request, session, url_for, abort
from app.utils.roles import is_admin_role, is_staff_role
from app.utils.landing import resolve_landing_endpoint

from app.models.user import User
from .config import Config
from .extensions import db, migrate, login_manager

from app.models.notification import Notification
from flask_login import current_user



def create_app():
    app = Flask(__name__)

    app.jinja_env.globals.update(is_admin_role=is_admin_role, is_staff_role=is_staff_role)

    from app.utils.text import (
        smart_title,
        normalize_spaces,
        role_label,
        status_label,
        flash_category_label,
    )

    app.jinja_env.filters["smart_title"] = smart_title
    app.jinja_env.filters["normalize_spaces"] = normalize_spaces
    app.jinja_env.filters["role_label"] = role_label
    app.jinja_env.filters["status_label"] = status_label
    app.jinja_env.filters["flash_category_label"] = flash_category_label


    app.config.from_object(Config)

    db.init_app(app)
    migrate.init_app(app, db)
    # IMPORTAR MODELOS PARA QUE ALEMBIC LOS DETECTE
    from .models.user import User  # noqa: F401
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    from . import models  # noqa: F401

    def _ensure_csrf_token() -> str:
        token = session.get("_csrf_token")
        if not token:
            token = secrets.token_urlsafe(32)
            session["_csrf_token"] = token
        return token

    from app.controllers.home_controller import home_bp
    app.register_blueprint(home_bp)

    from app.controllers.dashboard_controller import dashboard_bp
    app.register_blueprint(dashboard_bp)

    from app.controllers.notifications_controller import notifications_bp
    app.register_blueprint(notifications_bp)

    from .controllers.auth_controller import auth_bp
    app.register_blueprint(auth_bp)
    from app.controllers.profile_controller import profile_bp
    app.register_blueprint(profile_bp)

    from app.controllers.inventory_controller import inventory_bp
    app.register_blueprint(inventory_bp)
    from app.controllers.inventory_requests_controller import inventory_requests_bp
    app.register_blueprint(inventory_requests_bp)

    from app.controllers.api_controller import api_bp
    app.register_blueprint(api_bp)

    from app.controllers.debts_controller import debts_bp
    app.register_blueprint(debts_bp)

    from app.controllers.reservations_controller import reservations_bp
    app.register_blueprint(reservations_bp)

    from app.controllers.lostfound_controller import lostfound_bp
    app.register_blueprint(lostfound_bp)

    from app.controllers.software_controller import software_bp
    app.register_blueprint(software_bp)
    from app.controllers.print3d_controller import print3d_bp
    app.register_blueprint(print3d_bp)

    from app.controllers.reports_controller import reports_bp
    app.register_blueprint(reports_bp)

    from app.controllers.ra_client_controller import ra_client_bp
    app.register_blueprint(ra_client_bp)

    from app.controllers.users_controller import users_bp
    app.register_blueprint(users_bp)

    from app.controllers.forum_controller import forum_bp
    app.register_blueprint(forum_bp)

    from app.controllers.admin_extra_requests_controller import admin_extra_requests_bp
    app.register_blueprint(admin_extra_requests_bp)

    from app.controllers.legal_controller import legal_bp
    app.register_blueprint(legal_bp)
    @app.get("/")
    def root_home():
        if not current_user.is_authenticated:
            return redirect(url_for("auth.auth_page"))
        return redirect(url_for(resolve_landing_endpoint(current_user.role)))

    # Ruta de salud para verificar que el servidor está vivo
    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.context_processor
    def inject_notifications():
        if current_user.is_authenticated:
            notifs = (
                Notification.query
                .filter_by(user_id=current_user.id)
                .order_by(Notification.created_at.desc())
                .limit(5)
                .all()
            )

            unread = (
                Notification.query
                .filter(Notification.user_id == current_user.id, Notification.is_read.is_(False))
                .count()
            )

            return dict(
                header_notifications=notifs,
                header_unread_notifications=unread
            )

        return dict(header_notifications=[], header_unread_notifications=0)

    @app.context_processor
    def inject_csrf_token():
        return {"csrf_token": _ensure_csrf_token()}

    @app.before_request
    def enforce_profile_completion():
        _ensure_csrf_token()

        if not current_user.is_authenticated:
            return None

        if not getattr(current_user, "is_verified", False):
            return None

        if getattr(current_user, "profile_completed", False):
            return None

        endpoint = request.endpoint or ""
        allowed_endpoints = {
            "profile.complete_profile",
            "auth.logout",
            "static",
        }

        if endpoint in allowed_endpoints:
            return None

        return redirect(url_for("profile.complete_profile"))

    @app.before_request
    def enforce_csrf():
        if request.method not in {"POST", "PUT", "PATCH", "DELETE"}:
            return None

        endpoint = request.endpoint or ""
        if endpoint.startswith("api."):
            return None

        sent_token = request.form.get("csrf_token") or request.headers.get("X-CSRFToken")
        session_token = session.get("_csrf_token")
        if not session_token or not sent_token or sent_token != session_token:
            abort(400, description="CSRF token inválido o faltante.")

        return None

    return app
