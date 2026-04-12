from app import create_app
from app.extensions import db
from app.models.user import User
import os

app = create_app()

with app.app_context():
    email = (os.getenv("BOOTSTRAP_UNVERIFIED_EMAIL") or "").strip().lower()
    password = os.getenv("BOOTSTRAP_UNVERIFIED_PASSWORD") or ""

    if not email:
        raise SystemExit("Falta BOOTSTRAP_UNVERIFIED_EMAIL en entorno.")
    if len(password) < 10:
        raise SystemExit("BOOTSTRAP_UNVERIFIED_PASSWORD debe tener al menos 10 caracteres.")

    existing = User.query.filter_by(email=email).first()

    if existing:
        print("Ya existe ese usuario.")
    else:
        u = User(email=email, role="STUDENT", is_verified=False)
        u.set_password(password)
        db.session.add(u)
        db.session.commit()
        print("Usuario NO verificado creado:", email)
