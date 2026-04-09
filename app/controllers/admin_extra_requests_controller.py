from datetime import datetime

from flask import Blueprint, render_template, request, url_for
from flask_login import current_user

from app.models.critical_action_request import CriticalActionRequest
from app.models.inventory_request_ticket import InventoryRequestTicket
from app.models.print3d_job import Print3DJob
from app.models.profile_change_request import ProfileChangeRequest
from app.models.software import Software
from app.utils.authz import min_role_required
from app.utils.roles import is_admin_role


admin_extra_requests_bp = Blueprint("admin_extra_requests", __name__, url_prefix="/admin")


def _safe_text(value: str | None, fallback: str = "-") -> str:
    cleaned = (value or "").strip()
    return cleaned or fallback


def _to_record(*, req_type: str, req_id: int, requester: str, status: str, summary: str,
               created_at: datetime | None, link_admin: str | None, link_user: str | None,
               module: str) -> dict:
    return {
        "type": req_type,
        "id": req_id,
        "requester": requester,
        "status": status,
        "summary": summary,
        "created_at": created_at,
        "link_admin": link_admin,
        "link_user": link_user,
        "module": module,
    }


def _critical_action_records() -> list[dict]:
    rows = (
        CriticalActionRequest.query
        .order_by(CriticalActionRequest.created_at.desc())
        .limit(200)
        .all()
    )
    records: list[dict] = []
    for row in rows:
        requester = row.requester.email if row.requester else f"user:{row.requester_id}"
        target = row.target_user.email if row.target_user else f"user:{row.target_user_id}"
        records.append(_to_record(
            req_type="CRITICAL_ACTION",
            req_id=row.id,
            requester=requester,
            status=row.status,
            summary=f"{row.action_type} sobre {target}",
            created_at=row.created_at,
            link_admin=url_for("users.critical_action_requests"),
            link_user=url_for("users.critical_action_requests"),
            module="USERS",
        ))
    return records


def _profile_change_records() -> list[dict]:
    rows = (
        ProfileChangeRequest.query
        .order_by(ProfileChangeRequest.created_at.desc())
        .limit(200)
        .all()
    )
    records: list[dict] = []
    for row in rows:
        requester = row.user.email if row.user else f"user:{row.user_id}"
        summary = row.request_type
        if row.request_type == "PHONE_CHANGE" and row.requested_phone:
            summary = f"Cambio de teléfono a {row.requested_phone}"

        records.append(_to_record(
            req_type="PROFILE_CHANGE",
            req_id=row.id,
            requester=requester,
            status=row.status,
            summary=summary,
            created_at=row.created_at,
            link_admin=url_for("users.profile_change_requests"),
            link_user=None,
            module="USERS",
        ))
    return records


def _inventory_request_records() -> list[dict]:
    rows = (
        InventoryRequestTicket.query
        .order_by(InventoryRequestTicket.created_at.desc())
        .limit(200)
        .all()
    )
    records: list[dict] = []
    for row in rows:
        requester = row.user.email if row.user else f"user:{row.user_id}"
        summary = f"Solicitud de material ({row.request_date})"
        records.append(_to_record(
            req_type="INVENTORY_DAILY",
            req_id=row.id,
            requester=requester,
            status=row.status,
            summary=summary,
            created_at=row.created_at,
            link_admin=url_for("inventory_requests.admin_ticket_detail", ticket_id=row.id),
            link_user=url_for("inventory_requests.my_daily_request"),
            module="INVENTORY_REQUESTS",
        ))
    return records


def _software_update_records() -> list[dict]:
    rows = (
        Software.query
        .filter(Software.update_requested.is_(True))
        .order_by(Software.updated_at.desc(), Software.created_at.desc())
        .limit(200)
        .all()
    )
    records: list[dict] = []
    for row in rows:
        lab_name = row.lab.name if row.lab else "Sin laboratorio"
        summary = f"{row.name} ({lab_name})"
        if row.update_note:
            summary = f"{summary} · {row.update_note}"

        records.append(_to_record(
            req_type="SOFTWARE_UPDATE",
            req_id=row.id,
            requester="N/D",
            status="PENDING" if row.update_requested else "RESOLVED",
            summary=summary,
            created_at=row.updated_at or row.created_at,
            link_admin=url_for("software.list_software"),
            link_user=url_for("software.list_software"),
            module="SOFTWARE",
        ))
    return records


def _print3d_records() -> list[dict]:
    rows = (
        Print3DJob.query
        .order_by(Print3DJob.created_at.desc())
        .limit(200)
        .all()
    )
    records: list[dict] = []
    for row in rows:
        requester = row.requester_user.email if row.requester_user else f"user:{row.requester_user_id}"
        records.append(_to_record(
            req_type="PRINT3D",
            req_id=row.id,
            requester=requester,
            status=row.status,
            summary=_safe_text(row.title, fallback=f"Trabajo 3D #{row.id}"),
            created_at=row.created_at,
            link_admin=url_for("print3d.admin_list"),
            link_user=url_for("print3d.my_jobs"),
            module="PRINT3D",
        ))
    return records


def _pending_weight(status: str | None) -> int:
    normalized = (status or "").strip().upper()
    return 0 if normalized in {"PENDING", "OPEN", "REQUESTED", "QUOTED", "IN_PROGRESS", "READY_FOR_PICKUP"} else 1


@admin_extra_requests_bp.route("/extra-requests", methods=["GET"])
@min_role_required("ADMIN")
def admin_extra_requests_inbox():
    rows = []
    rows.extend(_critical_action_records())
    rows.extend(_profile_change_records())
    rows.extend(_inventory_request_records())
    rows.extend(_software_update_records())
    rows.extend(_print3d_records())

    selected_type = (request.args.get("type") or "").strip().upper()
    selected_status = (request.args.get("status") or "").strip().upper()
    q = (request.args.get("q") or "").strip().lower()

    if selected_type:
        rows = [r for r in rows if r["type"] == selected_type]

    if selected_status:
        rows = [r for r in rows if (r.get("status") or "").strip().upper() == selected_status]

    if q:
        rows = [
            r for r in rows
            if q in (r.get("requester") or "").lower()
            or q in (r.get("summary") or "").lower()
            or q in (r.get("module") or "").lower()
        ]

    rows.sort(key=lambda r: (_pending_weight(r.get("status")), -(r.get("created_at").timestamp() if r.get("created_at") else 0)))

    available_types = ["CRITICAL_ACTION", "PROFILE_CHANGE", "INVENTORY_DAILY", "SOFTWARE_UPDATE", "PRINT3D"]
    status_values = sorted({(r.get("status") or "").strip().upper() for r in rows if (r.get("status") or "").strip()})

    return render_template(
        "admin/extra_requests_inbox.html",
        rows=rows,
        selected_type=selected_type,
        selected_status=selected_status,
        q=q,
        available_types=available_types,
        available_statuses=status_values,
        active_page="extra_requests",
        can_access_admin=is_admin_role(current_user.role),
    )
