from typing import Optional

from flask_login import current_user

from app.models.permission import RolePermission


def has_permission(permission_name: str, role: Optional[str] = None) -> bool:
    current_role = role or getattr(current_user, "role", None)
    if not current_role:
        return False

    link = (
        RolePermission.query.join(RolePermission.permission)
        .filter(
            RolePermission.role == current_role,
            RolePermission.permission.has(name=permission_name),
        )
        .first()
    )

    return link is not None