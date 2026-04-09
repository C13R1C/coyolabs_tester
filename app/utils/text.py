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
    "STAFF": "Administrativo",
    "STUDENT": "Estudiante",
    "TEACHER": "Profesor",
    "SUPERADMIN": "Administrador",
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
    Print3DJobStatus.REQUESTED: "Solicitado",
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
