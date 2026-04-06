from app.extensions import db


class LostFound(db.Model):
    __tablename__ = "lost_found"

    id = db.Column(db.Integer, primary_key=True)

    # Quién lo reportó (puede ser admin o usuario)
    reported_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    reported_by = db.relationship("User", foreign_keys=[reported_by_user_id])

    # Opcional: ligado a un material del inventario si aplica
    material_id = db.Column(db.Integer, db.ForeignKey("materials.id"), nullable=True)
    material = db.relationship("Material")

    title = db.Column(db.String(160), nullable=False)      # nombre corto del objeto
    description = db.Column(db.Text, nullable=True)        # detalles
    location = db.Column(db.String(160), nullable=True)    # dónde se encontró o perdió

    # Evidencia simple por ahora (sin uploads): URL o texto
    evidence_ref = db.Column(db.String(255), nullable=True)

    # Workflow
    status = db.Column(db.String(20), nullable=False, default="REPORTED")  # REPORTED/IN_STORAGE/RETURNED
    admin_note = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)
    updated_at = db.Column(db.DateTime, onupdate=db.func.now())

    def __repr__(self) -> str:
        return f"<LostFound {self.id} {self.status} {self.title}>"
