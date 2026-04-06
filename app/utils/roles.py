import re
from typing import Optional

ROLE_PENDING = "PENDING"
ROLE_STUDENT = "STUDENT"
ROLE_TEACHER = "TEACHER"
ROLE_STAFF = "STAFF"
ROLE_ADMIN = "ADMIN"
ROLE_SUPERADMIN = "SUPERADMIN"


LEGACY_ROLE_ALIASES = {
    "USER": ROLE_STUDENT,
    "ALUMNO": ROLE_STUDENT,
    "PROFESOR": ROLE_TEACHER,
    "ADMINISTRATIVO": ROLE_STAFF,
    "PENDIENTE": ROLE_PENDING,
}


# ===== JERARQUÍA =====
ROLE_LEVEL = {
    ROLE_PENDING: 0,
    ROLE_STUDENT: 1,
    ROLE_TEACHER: 2,
    ROLE_STAFF: 3,
    ROLE_ADMIN: 4,
    ROLE_SUPERADMIN: 5,
}

ALL_ROLES = set(ROLE_LEVEL.keys())

ASSIGNABLE_ADMIN_ROLES = {
    ROLE_STUDENT,
    ROLE_TEACHER,
    ROLE_STAFF,
    ROLE_ADMIN,
}


# ===== REGLAS DE EMAIL =====
EMAIL_DOMAIN = "utpn.edu.mx"
STUDENT_EMAIL_RE = re.compile(r"^\d{8}@utpn\.edu\.mx$", re.IGNORECASE)
INSTITUTIONAL_NOMINAL_EMAIL_RE = re.compile(
    r"^[a-z]+(?:\.[a-z]+)*@utpn\.edu\.mx$",
    re.IGNORECASE,
)


# ===== NORMALIZACIÓN =====
def normalize_role(role: Optional[str]) -> Optional[str]:
    if role is None:
        return None

    normalized = role.strip().upper()
    if not normalized:
        return None

    return LEGACY_ROLE_ALIASES.get(normalized, normalized)


def role_level(role: Optional[str]) -> int:
    normalized = normalize_role(role)
    return ROLE_LEVEL.get(normalized, 0)


def role_at_least(user_role: Optional[str], required_role: Optional[str]) -> bool:
    normalized_required = normalize_role(required_role)
    if normalized_required not in ROLE_LEVEL:
        return False

    return role_level(user_role) >= ROLE_LEVEL[normalized_required]


def is_admin_role(role: Optional[str]) -> bool:
    normalized = normalize_role(role)
    return normalized in {ROLE_ADMIN, ROLE_SUPERADMIN}


def is_staff_role(role: Optional[str]) -> bool:
    normalized = normalize_role(role)
    return normalized in {ROLE_STAFF, ROLE_ADMIN, ROLE_SUPERADMIN}


def infer_role_from_email(email: Optional[str]) -> Optional[str]:
    normalized_email = (email or "").strip().lower()

    if not normalized_email.endswith(f"@{EMAIL_DOMAIN}"):
        return None

    if STUDENT_EMAIL_RE.match(normalized_email):
        return ROLE_STUDENT

    if INSTITUTIONAL_NOMINAL_EMAIL_RE.match(normalized_email):
        return ROLE_PENDING

    return None