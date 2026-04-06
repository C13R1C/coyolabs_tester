from functools import wraps

from flask import abort
from flask_login import current_user, login_required

from app.utils.roles import role_at_least, role_level


def min_role_required(min_role: str):
    """
    Permite min_role o superior usando jerarquía y aliases legacy.
    Uso:
      @min_role_required("STUDENT")
      @min_role_required("ADMIN")
      @min_role_required("SUPERADMIN")
      @min_role_required("STUDENT")
      @min_role_required("TEACHER")
      @min_role_required("STAFF")
    """
    min_level = role_level(min_role)

    def decorator(fn):
        @wraps(fn)
        @login_required
        def wrapper(*args, **kwargs):
            current_role = getattr(current_user, "role", None)
            if min_level <= 0 or not role_at_least(current_role, min_role):
                abort(403)
            return fn(*args, **kwargs)

        return wrapper

    return decorator
