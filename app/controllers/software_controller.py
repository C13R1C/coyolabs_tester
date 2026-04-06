from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import current_user

from app.extensions import db
from app.models.software import Software
from app.models.lab import Lab
from app.utils.authz import min_role_required
from app.utils.roles import is_admin_role


software_bp = Blueprint("software", __name__, url_prefix="/software")


@software_bp.route("/", methods=["GET"])
@min_role_required("STUDENT")
def software_home():
    if is_admin_role(current_user.role):
        return redirect(url_for("software.admin_new"))

    return redirect(url_for("software.list_software"))


@software_bp.route("/list", methods=["GET"])
@min_role_required("STUDENT")
def list_software():
    lab_id = request.args.get("lab_id", type=int)

    labs = Lab.query.order_by(Lab.name).all()
    q = Software.query

    if lab_id:
        q = q.filter(Software.lab_id == lab_id)

    items = q.order_by(Software.name.asc()).all()
    return render_template(
        "software/list.html",
        items=items,
        labs=labs,
        selected_lab=lab_id,
        active_page="software"
    )


@software_bp.route("/admin/new", methods=["GET", "POST"])
@min_role_required("ADMIN")
def admin_new():
    labs = Lab.query.order_by(Lab.name).all()

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

    return render_template("software/admin_new.html", labs=labs, active_page="software")


@software_bp.route("/<int:software_id>/request-update", methods=["POST"])
@min_role_required("STUDENT")
def request_update(software_id: int):
    s = Software.query.get(software_id)
    if not s:
        abort(404)

    note = (request.form.get("update_note") or "").strip()
    s.update_requested = True
    s.update_note = note or "Solicitud de actualización"
    db.session.commit()

    flash("Solicitud registrada.", "success")
    return redirect(url_for("software.list_software"))


@software_bp.route("/admin/<int:software_id>/clear-update", methods=["POST"])
@min_role_required("ADMIN")
def admin_clear_update(software_id: int):
    s = Software.query.get(software_id)
    if not s:
        abort(404)

    s.update_requested = False
    s.update_note = None
    db.session.commit()

    flash("Solicitud marcada como resuelta.", "success")
    return redirect(url_for("software.list_software"))