from datetime import datetime, time

from flask import Blueprint, redirect, render_template, request, url_for
from sqlalchemy.orm import joinedload
from flask_login import current_user, login_required

from app.utils.authz import min_role_required
from app.utils.roles import is_admin_role

from app.models.reservation import Reservation
from app.models.debt import Debt
from app.models.inventory_request_ticket import InventoryRequestTicket

home_bp = Blueprint("home", __name__, url_prefix="/home")

LAB_FLOORS = {
    "Primer piso": ["B001", "B002", "B003", "B004", "B005", "B006"],
    "Segundo piso": ["B101", "B102", "B103", "B104"],
}


def _parse_home_filters() -> tuple:
    time_str = request.args.get("time")

    selected_date = datetime.now().date()
    selected_time = time(11, 0)

    if time_str:
        try:
            selected_time = datetime.strptime(time_str, "%H:%M").time()
        except ValueError:
            pass

    return selected_date, selected_time


def _build_labs_status(selected_time, reservations):
    selected_time_str = selected_time.strftime("%H:%M")
    grouped = {}

    for floor_name, labs in LAB_FLOORS.items():
        floor_cards = []
        for lab in labs:
            status = "free"
            matched = None

            for reservation in reservations:
                if reservation.room != lab:
                    continue

                start_str = reservation.start_time.strftime("%H:%M")
                end_str = reservation.end_time.strftime("%H:%M")
                if not (start_str <= selected_time_str < end_str):
                    continue

                if reservation.status == "APPROVED":
                    status = "busy"
                    matched = reservation
                    break

                if reservation.status == "PENDING" and status != "busy":
                    status = "pending"
                    matched = reservation

            floor_cards.append(
                {
                    "lab": lab,
                    "status": status,
                    "reservation": matched,
                }
            )

        grouped[floor_name] = floor_cards

    return grouped


@home_bp.route("/labs", methods=["GET"])
@min_role_required("STUDENT")
def labs_view():
    # Compatibilidad con enlaces anteriores. La disponibilidad vive dentro del home.
    time_str = request.args.get("time")
    return redirect(url_for("home.home_dashboard", time=time_str, _anchor="labs"))


@home_bp.route("/", methods=["GET"])
@login_required
def home_dashboard():
    if is_admin_role(current_user.role):
        return redirect(url_for("dashboard.dashboard_home"))

    selected_date, selected_time = _parse_home_filters()

    user = current_user
    profile_completion_fields = [
        bool(user.full_name),
        bool(user.matricula),
        bool(user.career or user.career_rel),
        bool(user.academic_level or user.academic_level_rel),
        bool(user.phone),
    ]
    profile_completion_percent = int((sum(profile_completion_fields) / len(profile_completion_fields)) * 100)

    upcoming_reservations = (
        Reservation.query.filter(
            Reservation.user_id == user.id,
            Reservation.date >= selected_date,
        )
        .order_by(Reservation.date.asc(), Reservation.start_time.asc())
        .limit(5)
        .all()
    )

    recent_reservations = (
        Reservation.query.filter(Reservation.user_id == user.id)
        .order_by(Reservation.date.desc(), Reservation.start_time.desc())
        .limit(5)
        .all()
    )

    recent_tickets = (
        InventoryRequestTicket.query.filter(InventoryRequestTicket.user_id == user.id)
        .order_by(InventoryRequestTicket.created_at.desc())
        .limit(5)
        .all()
    )

    my_open_debts = (
        Debt.query.filter(Debt.user_id == user.id, Debt.status == "OPEN")
        .order_by(Debt.created_at.desc())
        .limit(5)
        .all()
    )

    labs_reservations = (
        Reservation.query.filter(Reservation.date == selected_date)
        .options(
            joinedload(Reservation.user),
            joinedload(Reservation.subject_rel),
        )
        .all()
    )
    labs_by_floor = _build_labs_status(selected_time, labs_reservations)

    return render_template(
        "home/home.html",
        active_page="home",
        profile_completion_percent=profile_completion_percent,
        is_profile_complete=bool(user.profile_completed),
        upcoming_reservations=upcoming_reservations,
        recent_reservations=recent_reservations,
        recent_tickets=recent_tickets,
        my_open_debts=my_open_debts,
        selected_date=selected_date,
        selected_time=selected_time.strftime("%H:%M"),
        labs_by_floor=labs_by_floor,
    )
