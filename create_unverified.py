from app import create_app
from app.extensions import db
from app.models.user import User

app = create_app()

with app.app_context():
    email = "00000000@utpn.edu.mx"
    existing = User.query.filter_by(email=email).first()

    if existing:
        print("Ya existe ese usuario.")
    else:
        u = User(email=email, role="STUDENT", is_verified=False)
        u.set_password("1234")
        db.session.add(u)
        db.session.commit()
        print("Usuario NO verificado creado:", email)
