from flask import Blueprint, render_template
from app.utils.authz import min_role_required

ra_client_bp = Blueprint("ra_client", __name__, url_prefix="/ra_client")

@ra_client_bp.route("/", methods=["GET"])
@min_role_required("STUDENT")  # acceso de estudiante
def ra_client_home():
    return render_template("ra_client/index.html", active_page="ra_client")