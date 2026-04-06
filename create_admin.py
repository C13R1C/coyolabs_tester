from app import create_app
from app.extensions import db
from app.models.user import User

app = create_app()

with app.app_context():
    email = "adminlab@utpn.edu.mx"

    existing = User.query.filter_by(email=email).first()

    if existing:
        print("Ya existe ese usuario, no se crea otro.")
    else:
        user = User(email=email, role="ADMIN", is_verified=True)
        user.set_password("1234")
        db.session.add(user)
        db.session.commit()
        print("Usuario creado:", email)
