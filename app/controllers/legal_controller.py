from flask import Blueprint, render_template


legal_bp = Blueprint("legal", __name__, url_prefix="/legal")


@legal_bp.route("/privacy", methods=["GET"])
def privacy_notice():
    return render_template("legal/privacy.html")


@legal_bp.route("/terms", methods=["GET"])
def terms_and_conditions():
    return render_template("legal/terms.html")
