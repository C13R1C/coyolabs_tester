from app.extensions import db


class Lab(db.Model):
    __tablename__ = "labs"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)

    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)

    def __repr__(self) -> str:
        return f"<Lab {self.name}>"
