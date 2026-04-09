from app.utils.roles import (
    ASSIGNABLE_ADMIN_ROLES,
    LEGACY_ROLE_ALIASES,
    ROLE_LEVEL,
    ROLE_PENDING,
    ROLE_STAFF,  # ← AQUÍ EL CAMBIO
    ROLE_ADMIN,           # ← agrega este también
    ROLE_STUDENT,
    ROLE_SUPERADMIN,
    ROLE_TEACHER,
)

ROOMS = [
    # Edificio B
    "B001", "B002", "B003", "B004", "B005", "B006",
    "B101", "B102", "B103", "B104",

    # Edificio E
    "E1", "E2", "E3", "E4", "E5", "E6",
]