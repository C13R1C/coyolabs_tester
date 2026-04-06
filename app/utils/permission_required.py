from functools import wraps

from flask import abort
from flask_login import current_user, login_required

from app.utils.permissions import has_permission


def permission_required(permission_name: str):
    def decorator(fn):
        @wraps(fn)
        @login_required
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)

            if not has_permission(permission_name):
                abort(403)

            return fn(*args, **kwargs)

        return wrapper

    return decorator