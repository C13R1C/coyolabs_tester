import re

from flask import Blueprint, current_app, render_template, request, redirect, url_for, flash, abort
from flask_login import current_user

from app.extensions import db
from app.models.software import Software
from app.models.lab import Lab
from app.services.notification_service import notify_roles, publish_notifications_safe
from app.utils.authz import min_role_required
from app.utils.roles import is_admin_role
from app.constants import ROOMS


software_bp = Blueprint("software", __name__, url_prefix="/software")


LAB_CODE_PATTERN = re.compile(r"^[A-Z]\d{3}$")


def _lab_room_code(lab: Lab | None) -> str | None:
    if not lab:
        return None
    candidate = ((lab.code or "").strip() or (lab.name or "").strip()).upper()
    return candidate if LAB_CODE_PATTERN.match(candidate) else None


def _room_labs_context() -> tuple[list[Lab], dict[int, str | None]]:
    labs = Lab.query.order_by(Lab.name).all()
    lab_room_codes = {lab.id: _lab_room_code(lab) for lab in labs}
    room_labs = [lab for lab in labs if lab_room_codes.get(lab.id)]
    return room_labs, lab_room_codes


@software_bp.route("/", methods=["GET"])
@min_role_required("STUDENT")
def software_home():
    return redirect(url_for("software.list_software"))


@software_bp.route("/list", methods=["GET"])
@min_role_required("STUDENT")
def list_software():
    lab_id = request.args.get("lab_id", type=int)

    filter_labs, lab_room_codes = _room_labs_context()
    q = Software.query

    if lab_id:
        q = q.filter(Software.lab_id == lab_id)

    items = q.order_by(Software.name.asc()).all()
    return render_template(
        "software/list.html",
        items=items,
        labs=filter_labs,
        lab_room_codes=lab_room_codes,
        selected_lab=lab_id,
        active_page="software"
    )


@software_bp.route("/admin/new", methods=["GET", "POST"])
@min_role_required("ADMIN")
def admin_new():
    labs, lab_room_codes = _room_labs_context()

    if request.method == "POST":
        lab_id = request.form.get("lab_id", type=int)
        name = (request.form.get("name") or "").strip()
        version = (request.form.get("version") or "").strip()
        license_type = (request.form.get("license_type") or "").strip()
        notes = (request.form.get("notes") or "").strip()

        if not name:
            flash("El nombre del software es obligatorio.", "error")
            return redirect(url_for("software.admin_new"))

        lab = None
        if lab_id:
            lab = Lab.query.get(lab_id)
            if not lab:
                flash("lab_id inválido.", "error")
                return redirect(url_for("software.admin_new"))
            if not lab_room_codes.get(lab.id):
                flash("Selecciona un salón/laboratorio válido.", "error")
                return redirect(url_for("software.admin_new"))

        s = Software(
            lab_id=lab.id if lab else None,
            name=name,
            version=version or None,
            license_type=license_type or None,
            notes=notes or None,
            update_requested=False,
            update_note=None,
        )
        db.session.add(s)
        db.session.commit()

        flash("Software agregado.", "success")
        return redirect(url_for("software.list_software"))

    return render_template(
        "software/admin_new.html",
        labs=labs,
        lab_room_codes=lab_room_codes,
        active_page="software",
    )


@software_bp.route("/admin/<int:software_id>/edit", methods=["GET", "POST"])
@min_role_required("ADMIN")
def admin_edit(software_id: int):
    s = Software.query.get_or_404(software_id)
    labs, lab_room_codes = _room_labs_context()

    if request.method == "POST":
        lab_id = request.form.get("lab_id", type=int)
        name = (request.form.get("name") or "").strip()
        version = (request.form.get("version") or "").strip()
        license_type = (request.form.get("license_type") or "").strip()
        notes = (request.form.get("notes") or "").strip()

        if not name:
            flash("El nombre del software es obligatorio.", "error")
            return redirect(url_for("software.admin_edit", software_id=s.id))

        lab = None
        if lab_id:
            lab = Lab.query.get(lab_id)
            if not lab:
                flash("lab_id inválido.", "error")
                return redirect(url_for("software.admin_edit", software_id=s.id))
            if not lab_room_codes.get(lab.id):
                flash("Selecciona un salón/laboratorio válido.", "error")
                return redirect(url_for("software.admin_edit", software_id=s.id))

        s.lab_id = lab.id if lab else None
        s.name = name
        s.version = version or None
        s.license_type = license_type or None
        s.notes = notes or None
        db.session.commit()

        flash("Software actualizado.", "success")
        return redirect(url_for("software.list_software"))

    return render_template(
        "software/admin_edit.html",
        software=s,
        labs=labs,
        lab_room_codes=lab_room_codes,
        active_page="software",
    )


@software_bp.route("/<int:software_id>/request-update", methods=["POST"])
@min_role_required("STUDENT")
def request_update(software_id: int):
    s = Software.query.get(software_id)
    if not s:
        abort(404)

    note = (request.form.get("update_note") or "").strip()
    s.update_requested = True
    s.update_note = note or "Seguimiento técnico solicitado"
    notifications = notify_roles(
        roles=["ADMIN", "SUPERADMIN", "STAFF"],
        title="Nueva solicitud técnica de software",
        message="Se registró una solicitud técnica de software.",
        link=url_for("software.list_software"),
        actor_name=(current_user.full_name or current_user.email),
        entity_name=s.name,
        extra_context=(note or None),
        priority="low",
    )
    db.session.commit()
    publish_notifications_safe(
        notifications,
        logger=current_app.logger,
        event_label="software update request",
        extra={"software_id": s.id},
    )

    flash("Seguimiento técnico registrado.", "success")
    return redirect(url_for("software.list_software"))


@software_bp.route("/admin/<int:software_id>/clear-update", methods=["POST"])
@min_role_required("ADMIN")
def admin_clear_update(software_id: int):
    s = Software.query.get(software_id)
    if not s:
        abort(404)

    s.update_requested = False
    s.update_note = None
    notifications = notify_roles(
        roles=["ADMIN", "SUPERADMIN", "STAFF"],
        title="Solicitud técnica atendida",
        message="La solicitud técnica fue marcada como atendida.",
        link=url_for("software.list_software"),
        actor_name=(current_user.full_name or current_user.email),
        entity_name=s.name,
        priority="medium",
    )
    db.session.commit()
    publish_notifications_safe(
        notifications,
        logger=current_app.logger,
        event_label="software update clear",
        extra={"software_id": s.id},
    )

    flash("Seguimiento marcado como atendido.", "success")
    return redirect(url_for("software.list_software"))
