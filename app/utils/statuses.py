"""Centralized status constants for domain workflows."""


class ReservationStatus:
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CANCELED = "CANCELLED"
    CANCELLED = CANCELED


class LabTicketStatus:
    OPEN = "OPEN"
    READY_FOR_PICKUP = "READY_FOR_PICKUP"
    CLOSURE_REQUESTED = "CLOSURE_REQUESTED"
    CLOSED = "CLOSED"
    CLOSED_WITH_DEBT = "CLOSED_WITH_DEBT"


class TicketItemStatus:
    PENDING = "PENDING"
    REQUESTED = PENDING  # alias legacy para compatibilidad en código existente
    DELIVERED = "DELIVERED"
    RETURNED = "RETURNED"
    READY_FOR_PICKUP = PENDING  # alias legacy: ya no se persiste como estado de ítem
    MISSING = DELIVERED  # alias legacy: faltante se infiere por cantidades, no por estado DB


class DebtStatus:
    PENDING = "PENDING"
    PAID = "PAID"
    CANCELED = "CANCELLED"
    CANCELLED = CANCELED

    # Alias legacy para compatibilidad con código antiguo
    OPEN = PENDING


class InventoryRequestStatus:
    OPEN = "OPEN"
    READY = "READY"
    READY_FOR_PICKUP = READY  # alias legacy para compatibilidad de código
    CLOSED = "CLOSED"


class Print3DJobStatus:
    REQUESTED = "REQUESTED"
    QUOTED = "QUOTED"
    IN_PROGRESS = "IN_PROGRESS"
    READY = "READY"
    READY_FOR_PICKUP = "READY_FOR_PICKUP"
    DELIVERED = "DELIVERED"
    CANCELED = "CANCELED"


PRINT3D_ALLOWED_STATUSES = {
    Print3DJobStatus.REQUESTED,
    Print3DJobStatus.QUOTED,
    Print3DJobStatus.IN_PROGRESS,
    Print3DJobStatus.READY,
    Print3DJobStatus.READY_FOR_PICKUP,
    Print3DJobStatus.DELIVERED,
    Print3DJobStatus.CANCELED,
}


PRINT3D_ALLOWED_TRANSITIONS = {
    Print3DJobStatus.REQUESTED: {Print3DJobStatus.QUOTED, Print3DJobStatus.CANCELED},
    Print3DJobStatus.QUOTED: {Print3DJobStatus.IN_PROGRESS, Print3DJobStatus.CANCELED},
    Print3DJobStatus.IN_PROGRESS: {Print3DJobStatus.READY, Print3DJobStatus.CANCELED},
    Print3DJobStatus.READY: {Print3DJobStatus.READY_FOR_PICKUP, Print3DJobStatus.CANCELED},
    Print3DJobStatus.READY_FOR_PICKUP: {Print3DJobStatus.DELIVERED, Print3DJobStatus.CANCELED},
    Print3DJobStatus.DELIVERED: set(),
    Print3DJobStatus.CANCELED: set(),
}


ACTIVE_LAB_TICKET_STATUSES = {
    LabTicketStatus.OPEN,
    LabTicketStatus.READY_FOR_PICKUP,
}

BLOCKING_LAB_TICKET_STATUSES = ACTIVE_LAB_TICKET_STATUSES | {LabTicketStatus.CLOSURE_REQUESTED}


def normalize_status(status: str | None) -> str:
    return (status or "").strip().upper()


def is_active_lab_ticket_status(status: str | None) -> bool:
    return normalize_status(status) in ACTIVE_LAB_TICKET_STATUSES


def is_lab_ticket_closure_requested(status: str | None) -> bool:
    return normalize_status(status) == LabTicketStatus.CLOSURE_REQUESTED
