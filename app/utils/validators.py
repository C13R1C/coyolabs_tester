import re

PHONE_ALLOWED_RE = re.compile(r"^[0-9+\-\s().]+$")
GROUP_CODE_RE = re.compile(r"^[A-Z0-9-]{2,20}$")
UTPN_EMAIL_RE = re.compile(r"^[^@\s]+@utpn\.edu\.mx$")


def normalize_and_validate_phone(raw_phone: str | None) -> tuple[str | None, str | None]:
    phone = " ".join((raw_phone or "").strip().split())
    if not phone:
        return None, "Debes capturar un teléfono."

    if not PHONE_ALLOWED_RE.match(phone):
        return None, "El teléfono contiene caracteres no permitidos."

    digits = "".join(ch for ch in phone if ch.isdigit())
    if len(digits) < 8 or len(digits) > 15:
        return None, "El teléfono debe tener entre 8 y 15 dígitos."

    if len(phone) > 25:
        return None, "El teléfono excede la longitud máxima permitida."

    return phone, None


def normalize_and_validate_group_code(raw_group_code: str | None) -> tuple[str | None, str | None]:
    group_code = (raw_group_code or "").strip().upper()
    if not group_code:
        return None, "El grupo es obligatorio."

    if not GROUP_CODE_RE.match(group_code):
        return None, "El grupo debe tener 2-20 caracteres alfanuméricos (A-Z, 0-9, -)."

    return group_code, None


def is_valid_utpn_email(email: str) -> bool:
    return bool(UTPN_EMAIL_RE.match((email or "").strip().lower()))
