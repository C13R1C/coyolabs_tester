"""Dashboard administrativo principal para ADMIN/SUPERADMIN."""

from datetime import datetime, timedelta

from flask import Blueprint, jsonify, render_template, request, url_for
from flask_login import current_user
from sqlalchemy import func
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.models.material import Material
from app.models.reservation import Reservation
from app.models.lab_ticket import LabTicket
from app.models.ticket_item import TicketItem
from app.models.debt import Debt
from app.models.notification import Notification
from app.models.print3d_job import Print3DJob
from app.models.software import Software
from app.models.user import User
from app.utils.authz import min_role_required
from app.constants import ROLE_PENDING
from app.utils.statuses import DebtStatus, LabTicketStatus, Print3DJobStatus, ReservationStatus, TicketItemStatus

dashboard_bp = Blueprint("dashboard", __name__, url_prefix="/dashboard")


def _search_reports_base() -> list[dict]:
    return [
        {
            "title": "Inventario general",
            "description": "Materiales por laboratorio, estado, código y ubicación.",
            "tags": "inventario materiales laboratorio estado código ubicación",
            "link": url_for("reports.report_inventory_view"),
        },
        {
            "title": "Adeudos",
            "description": "Seguimiento de adeudos activos y cerrados.",
            "tags": "adeudos deudas pagos",
            "link": url_for("reports.report_debts_view"),
        },
        {
            "title": "Bitácora",
            "description": "Eventos administrativos y de operación.",
            "tags": "bitácora auditoría eventos logs",
            "link": url_for("reports.report_logbook_view"),
        },
        {
            "title": "Reservaciones",
            "description": "Reservas por salón, docente, grupo y estado.",
            "tags": "reservaciones calendario salones",
            "link": url_for("reports.report_reservations_view"),
        },
        {
            "title": "Objetos perdidos",
            "description": "Incidencias y estado de objetos reportados.",
            "tags": "objetos perdidos encontrados",
            "link": url_for("reports.report_lostfound_view"),
        },
        {
            "title": "Software",
            "description": "Inventario de software y seguimiento técnico.",
            "tags": "software licencias versiones seguimiento",
            "link": url_for("reports.report_software_view"),
        },
    ]


def _build_operational_snapshot(activity_limit: int = 8) -> dict:
    today = datetime.now().date()
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)

    counts_row = db.session.query(
        db.select(func.count(Reservation.id))
        .where(Reservation.status == ReservationStatus.PENDING)
        .scalar_subquery()
        .label("pending_reservations"),
        db.select(func.count(LabTicket.id))
        .where(LabTicket.status.in_([LabTicketStatus.OPEN, LabTicketStatus.READY_FOR_PICKUP]))
        .scalar_subquery()
        .label("active_tickets"),
        db.select(func.count(TicketItem.id))
        .where(TicketItem.status == TicketItemStatus.READY_FOR_PICKUP)
        .scalar_subquery()
        .label("ready_items"),
        db.select(func.count(LabTicket.id))
        .where(LabTicket.status == LabTicketStatus.CLOSURE_REQUESTED)
        .scalar_subquery()
        .label("closure_requested_tickets"),
        db.select(func.count(Debt.id))
        .where(Debt.status == DebtStatus.PENDING)
        .scalar_subquery()
        .label("open_debts"),
        db.select(func.count(Print3DJob.id))
        .where(Print3DJob.status == Print3DJobStatus.REQUESTED)
        .scalar_subquery()
        .label("pending_print3d_jobs"),
    ).first()

    reservation_counts = db.session.query(
        func.count(Reservation.id).label("reservations_today"),
        func.sum(db.case((Reservation.status == ReservationStatus.APPROVED, 1), else_=0)).label("approved_today"),
        func.sum(db.case((Reservation.status == ReservationStatus.PENDING, 1), else_=0)).label("pending_today"),
    ).filter(Reservation.date == today).first()

    ticket_debt_counts = db.session.query(
        db.select(func.count(LabTicket.id))
        .where(LabTicket.status == LabTicketStatus.OPEN)
        .scalar_subquery()
        .label("open_tickets"),
        db.select(func.count(LabTicket.id))
        .where(LabTicket.status == LabTicketStatus.CLOSED_WITH_DEBT)
        .scalar_subquery()
        .label("closed_with_debt"),
        db.select(func.count(Debt.id))
        .where(Debt.status == DebtStatus.PENDING)
        .scalar_subquery()
        .label("open_debts"),
    ).first()

    total_inventory = Material.query.count()
    low_stock_count = Material.query.filter(
        Material.pieces_qty.isnot(None),
        Material.pieces_qty <= 3
    ).count()
    pending_users_count = User.query.filter(User.role == ROLE_PENDING).count()
    weekly_reservations = Reservation.query.filter(
        Reservation.date >= week_start,
        Reservation.date <= week_end
    ).count()

    pending_reservations = (
        Reservation.query
        .options(joinedload(Reservation.user))
        .filter(Reservation.status == ReservationStatus.PENDING)
        .order_by(Reservation.created_at.asc())
        .limit(activity_limit)
        .all()
    )

    active_tickets = (
        LabTicket.query
        .options(joinedload(LabTicket.owner_user), joinedload(LabTicket.reservation))
        .filter(LabTicket.status.in_([LabTicketStatus.OPEN, LabTicketStatus.READY_FOR_PICKUP]))
        .order_by(LabTicket.opened_at.asc())
        .limit(activity_limit)
        .all()
    )

    ready_items = (
        TicketItem.query
        .options(
            joinedload(TicketItem.ticket).joinedload(LabTicket.owner_user),
            joinedload(TicketItem.material),
        )
        .filter(TicketItem.status == TicketItemStatus.READY_FOR_PICKUP)
        .order_by(TicketItem.id.desc())
        .limit(activity_limit)
        .all()
    )

    closure_requested = (
        LabTicket.query
        .options(joinedload(LabTicket.owner_user), joinedload(LabTicket.reservation))
        .filter(LabTicket.status == LabTicketStatus.CLOSURE_REQUESTED)
        .order_by(LabTicket.opened_at.asc())
        .limit(activity_limit)
        .all()
    )

    open_debts_recent = (
        Debt.query
        .options(joinedload(Debt.user), joinedload(Debt.material))
        .filter(Debt.status == DebtStatus.PENDING)
        .order_by(Debt.created_at.desc())
        .limit(activity_limit)
        .all()
    )

    pending_print3d_recent = (
        Print3DJob.query
        .filter(Print3DJob.status == Print3DJobStatus.REQUESTED)
        .order_by(Print3DJob.created_at.desc())
        .limit(activity_limit)
        .all()
    )

    recent_activity = (
        Notification.query
        .filter(Notification.user_id == current_user.id)
        .order_by(Notification.created_at.desc())
        .limit(activity_limit)
        .all()
    )

    return {
        "counts": {
            "pending_reservations": int(counts_row.pending_reservations or 0),
            "active_tickets": int(counts_row.active_tickets or 0),
            "ready_items": int(counts_row.ready_items or 0),
            "closure_requested_tickets": int(counts_row.closure_requested_tickets or 0),
            "open_debts": int(counts_row.open_debts or 0),
            "pending_print3d_jobs": int(counts_row.pending_print3d_jobs or 0),
        },
        "pending_reservations": [
            {
                "id": r.id,
                "user": r.user.email if r.user else "-",
                "room": r.room,
                "date": str(r.date),
                "time": f"{r.start_time}-{r.end_time}",
                "link": "/reservations/admin",
            }
            for r in pending_reservations
        ],
        "active_tickets": [
            {
                "id": t.id,
                "status": t.status,
                "user": t.owner_user.email if t.owner_user else "-",
                "reservation_id": t.reservation_id,
                "room": t.room or "-",
                "link": f"/reservations/admin/tickets/{t.id}",
            }
            for t in active_tickets
        ],
        "ready_items": [
            {
                "ticket_id": item.ticket_id,
                "material": item.material.name if item.material else f"ID {item.material_id}",
                "quantity_requested": item.quantity_requested,
                "quantity_delivered": item.quantity_delivered,
                "user": item.ticket.owner_user.email if item.ticket and item.ticket.owner_user else "-",
                "link": f"/reservations/admin/tickets/{item.ticket_id}",
            }
            for item in ready_items
        ],
        "closure_requested_tickets": [
            {
                "id": t.id,
                "user": t.owner_user.email if t.owner_user else "-",
                "reservation_id": t.reservation_id,
                "room": t.room or "-",
                "link": f"/reservations/admin/tickets/{t.id}",
            }
            for t in closure_requested
        ],
        "open_debts_recent": [
            {
                "id": d.id,
                "user": d.user.email if d.user else "-",
                "material": d.material.name if d.material else "-",
                "created_at": str(d.created_at),
                "link": "/debts/admin",
            }
            for d in open_debts_recent
        ],
        "pending_print3d_recent": [
            {
                "id": job.id,
                "title": job.title,
                "status": job.status,
                "created_at": str(job.created_at),
                "link": "/prints3d/admin",
            }
            for job in pending_print3d_recent
        ],
        "recent_activity": [
            {
                "title": n.title,
                "message": n.message,
                "created_at": str(n.created_at),
                "link": n.link or "/notifications",
            }
            for n in recent_activity
        ],
        "summary": {
            "total_inventory": int(total_inventory or 0),
            "reservations_today": int(reservation_counts.reservations_today or 0),
            "approved_today": int(reservation_counts.approved_today or 0),
            "pending_today": int(reservation_counts.pending_today or 0),
            "open_tickets": int(ticket_debt_counts.open_tickets or 0),
            "closed_with_debt": int(ticket_debt_counts.closed_with_debt or 0),
            "open_debts": int(ticket_debt_counts.open_debts or 0),
            "low_stock_count": int(low_stock_count or 0),
            "pending_users_count": int(pending_users_count or 0),
            "weekly_reservations": int(weekly_reservations or 0),
            "pending_print3d_jobs": int(counts_row.pending_print3d_jobs or 0),
        },
    }


@dashboard_bp.route("/", methods=["GET"])
@min_role_required("ADMIN")
def dashboard_home():
    today = datetime.now().date()
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)

    reservation_counts = db.session.query(
        func.count(Reservation.id).label("reservations_today"),
        func.sum(db.case((Reservation.status == ReservationStatus.APPROVED, 1), else_=0)).label("approved_today"),
        func.sum(db.case((Reservation.status == ReservationStatus.PENDING, 1), else_=0)).label("pending_today"),
    ).filter(Reservation.date == today).first()

    ticket_debt_counts = db.session.query(
        db.select(func.count(LabTicket.id))
        .where(LabTicket.status == LabTicketStatus.OPEN)
        .scalar_subquery()
        .label("open_tickets"),
        db.select(func.count(LabTicket.id))
        .where(LabTicket.status == LabTicketStatus.CLOSED_WITH_DEBT)
        .scalar_subquery()
        .label("closed_with_debt"),
        db.select(func.count(Debt.id))
        .where(Debt.status == DebtStatus.PENDING)
        .scalar_subquery()
        .label("open_debts"),
    ).first()

    total_inventory = Material.query.count()

    reservations_today = int(reservation_counts.reservations_today or 0)
    approved_today = int(reservation_counts.approved_today or 0)
    pending_today = int(reservation_counts.pending_today or 0)
    open_tickets = int(ticket_debt_counts.open_tickets or 0)
    closed_with_debt = int(ticket_debt_counts.closed_with_debt or 0)
    open_debts = int(ticket_debt_counts.open_debts or 0)

    low_stock_count = Material.query.filter(
        Material.pieces_qty.isnot(None),
        Material.pieces_qty <= 3
    ).count()
    pending_users_count = User.query.filter(User.role == ROLE_PENDING).count()

    weekly_reservations = Reservation.query.filter(
        Reservation.date >= week_start,
        Reservation.date <= week_end
    ).count()

    recent_reservations = (
        Reservation.query
        .options(joinedload(Reservation.user))
        .order_by(Reservation.created_at.desc())
        .limit(5)
        .all()
    )

    recent_tickets = (
        LabTicket.query
        .options(joinedload(LabTicket.owner_user), joinedload(LabTicket.reservation))
        .order_by(LabTicket.opened_at.desc())
        .limit(5)
        .all()
    )

    recent_debts = (
        Debt.query
        .options(joinedload(Debt.user), joinedload(Debt.material))
        .order_by(Debt.created_at.desc())
        .limit(5)
        .all()
    )

    top_materials = (
        db.session.query(
            Material.name,
            func.coalesce(func.sum(TicketItem.quantity_requested), 0).label("total")
        )
        .join(TicketItem, TicketItem.material_id == Material.id)
        .group_by(Material.id, Material.name)
        .order_by(func.sum(TicketItem.quantity_requested).desc())
        .limit(5)
        .all()
    )

    top_debtors = (
        db.session.query(
            User.email,
            func.count(Debt.id).label("total_open")
        )
        .join(Debt, Debt.user_id == User.id)
        .filter(Debt.status == DebtStatus.PENDING)
        .group_by(User.id, User.email)
        .order_by(func.count(Debt.id).desc())
        .limit(5)
        .all()
    )

    top_rooms = (
        db.session.query(
            Reservation.room,
            func.count(Reservation.id).label("total")
        )
        .group_by(Reservation.room)
        .order_by(func.count(Reservation.id).desc())
        .limit(5)
        .all()
    )

    return render_template(
        "dashboard/home.html",
        active_page="dashboard",
        total_inventory=total_inventory,
        reservations_today=reservations_today,
        approved_today=approved_today,
        pending_today=pending_today,
        open_tickets=open_tickets,
        closed_with_debt=closed_with_debt,
        open_debts=open_debts,
        low_stock_count=low_stock_count,
        pending_users_count=pending_users_count,
        weekly_reservations=weekly_reservations,
        recent_reservations=recent_reservations,
        recent_tickets=recent_tickets,
        recent_debts=recent_debts,
        top_materials=top_materials,
        top_debtors=top_debtors,
        top_rooms=top_rooms,
        ops_snapshot=_build_operational_snapshot(),
    )


@dashboard_bp.route("/ops-feed", methods=["GET"])
@min_role_required("ADMIN")
def dashboard_ops_feed():
    return jsonify(_build_operational_snapshot())


@dashboard_bp.route("/search", methods=["GET"])
@min_role_required("ADMIN")
def dashboard_quick_search():
    search_text = (request.args.get("q") or "").strip()

    inventory_items = (
        Material.query
        .options(joinedload(Material.career), joinedload(Material.lab))
        .order_by(Material.created_at.desc())
        .limit(30)
        .all()
    )

    software_items = (
        Software.query
        .options(joinedload(Software.lab))
        .order_by(Software.created_at.desc())
        .limit(30)
        .all()
    )

    report_items = _search_reports_base()

    return render_template(
        "dashboard/search.html",
        inventory_items=inventory_items,
        software_items=software_items,
        report_items=report_items,
        search_text=search_text,
        active_page="dashboard",
    )
