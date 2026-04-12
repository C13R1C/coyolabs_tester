from app import create_app
from app.extensions import db
from app.models.user import User
import os

app = create_app()

with app.app_context():
    email = (os.getenv("BOOTSTRAP_ADMIN_EMAIL") or "").strip().lower()
    password = os.getenv("BOOTSTRAP_ADMIN_PASSWORD") or ""

    if not email:
        raise SystemExit("Falta BOOTSTRAP_ADMIN_EMAIL en entorno.")
    if len(password) < 10:
        raise SystemExit("BOOTSTRAP_ADMIN_PASSWORD debe tener al menos 10 caracteres.")

    existing = User.query.filter_by(email=email).first()

    if existing:
        print("Ya existe ese usuario, no se crea otro.")
    else:
        user = User(email=email, role="ADMIN", is_verified=True)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        print("Usuario creado:", email)
