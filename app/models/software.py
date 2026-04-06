from app.extensions import db


class Software(db.Model):
    __tablename__ = "software"

    id = db.Column(db.Integer, primary_key=True)

    # Relacionado a un lab (si usas Lab)
    lab_id = db.Column(db.Integer, db.ForeignKey("labs.id"), nullable=True)
    lab = db.relationship("Lab")

    name = db.Column(db.String(160), nullable=False)          # ej. "Visual Studio Code"
    version = db.Column(db.String(60), nullable=True)         # ej. "1.86"
    license_type = db.Column(db.String(60), nullable=True)    # ej. "Free", "Institutional"
    notes = db.Column(db.Text, nullable=True)

    # Solicitud de actualización (simple)
    update_requested = db.Column(db.Boolean, nullable=False, default=False)
    update_note = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)
    updated_at = db.Column(db.DateTime, onupdate=db.func.now())

    def __repr__(self) -> str:
        return f"<Software {self.id} {self.name}>"
