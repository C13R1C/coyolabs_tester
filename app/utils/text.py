import re
from app.utils.statuses import (
    DebtStatus,
    InventoryRequestStatus,
    LabTicketStatus,
    Print3DJobStatus,
    ReservationStatus,
    TicketItemStatus,
)

ROLE_LABELS = {
    "ADMIN": "Administrador",
    "STAFF": "Staff",
    "STUDENT": "Estudiante",
    "TEACHER": "Profesor",
    "SUPERADMIN": "Superadministrador",
    "PENDING": "Pendiente",
}

STATUS_LABELS = {
    ReservationStatus.APPROVED: "Aprobado",
    ReservationStatus.PENDING: "Pendiente",
    ReservationStatus.REJECTED: "Rechazado",
    InventoryRequestStatus.OPEN: "Abierto",
    InventoryRequestStatus.CLOSED: "Cerrado",
    "IN_PROGRESS": "En curso",
    "COMPLETED": "Completado",
    LabTicketStatus.CLOSED_WITH_DEBT: "Cerrado con adeudo",
    "READY": "Listo para recoger",
    LabTicketStatus.READY_FOR_PICKUP: "Listo para recoger",
    LabTicketStatus.CLOSURE_REQUESTED: "Cierre solicitado",
    "REPORTED": "Reportado",
    "IN_STORAGE": "En resguardo",
    TicketItemStatus.RETURNED: "Devuelto",
    DebtStatus.PENDING: "Pendiente",
    DebtStatus.PAID: "Pagado",
    "CANCELLED": "Cancelado",
    DebtStatus.CANCELED: "Cancelado",
    Print3DJobStatus.REQUESTED: "En revisión",
    Print3DJobStatus.QUOTED: "Cotizado",
    Print3DJobStatus.IN_PROGRESS: "En proceso",
    Print3DJobStatus.READY: "Listo",
    Print3DJobStatus.READY_FOR_PICKUP: "Listo para recoger",
    Print3DJobStatus.DELIVERED: "Entregado",
    Print3DJobStatus.CANCELED: "Cancelado",
}

FLASH_CATEGORY_LABELS = {
    "success": "Operación realizada correctamente",
    "error": "Ocurrió un error",
    "danger": "Ocurrió un error",
    "invalid": "Datos inválidos",
    "warning": "Atención",
    "warn": "Atención",
    "info": "Información",
}


def normalize_spaces(s: str) -> str:
    s = (s or "").strip()
    s = re.sub(r"\s+", " ", s)
    return s


def smart_title(s: str) -> str:
    s = normalize_spaces(s)
    if not s:
        return s

    if s.isupper():
        return " ".join([w if any(ch.isdigit() for ch in w) else w.capitalize() for w in s.lower().split(" ")])

    return s


def role_label(role: str | None) -> str:
    normalized = normalize_spaces(role or "").upper()
    return ROLE_LABELS.get(normalized, role or "")


def status_label(status: str | None) -> str:
    normalized = normalize_spaces(status or "").upper()
    return STATUS_LABELS.get(normalized, status or "")


def flash_category_label(category: str | None) -> str:
    normalized = normalize_spaces(category or "info").lower()
    return FLASH_CATEGORY_LABELS.get(normalized, "Información")


def normalize_lab_room_code(room: str | None) -> str:
    """Normaliza códigos como E001/E01/E1 al formato canónico E1."""
    value = normalize_spaces(room or "").upper()
    match = re.match(r"^([A-Z])0*(\d+)$", value)
    if not match:
        return value
    building, number = match.groups()
    return f"{building}{int(number)}"


def lab_room_code_variants(room: str | None) -> set[str]:
    """Genera variantes mínimas para comparaciones sin migrar datos."""
    canonical = normalize_lab_room_code(room)
    match = re.match(r"^([A-Z])(\d+)$", canonical)
    if not match:
        return {canonical} if canonical else set()
    building, number = match.groups()
    padded = f"{building}{int(number):03d}"
    return {canonical, padded}
