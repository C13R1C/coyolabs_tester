from flask import Blueprint, render_template
from flask_login import current_user

from app.utils.authz import min_role_required
from app.utils.roles import is_admin_role

ra_client_bp = Blueprint("ra_client", __name__, url_prefix="/ra_client")


@ra_client_bp.route("/", methods=["GET"])
@min_role_required("STUDENT")  # STUDENT+ (incluye TEACHER/STAFF/ADMIN/SUPERADMIN)
def ra_client_home():
    return render_template(
        "ra_client/index.html",
        active_page="ra_client",
        ra_api_base_url="/api/ra",
        ra_user_email=getattr(current_user, "email", ""),
        can_view_ra_tools=is_admin_role(getattr(current_user, "role", None)),
    )
