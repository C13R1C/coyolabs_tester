from app.extensions import db


class LogbookEvent(db.Model):
    __tablename__ = "logbook_events"

    id = db.Column(db.Integer, primary_key=True)

    # Quién hizo la acción (nullable para eventos automáticos o sistema)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    user = db.relationship("User", backref="logbook_events")

    # Sobre qué material (nullable si no aplica)
    material_id = db.Column(db.Integer, db.ForeignKey("materials.id"), nullable=True)
    material = db.relationship("Material", backref="logbook_events")

    # Acción/evento
    action = db.Column(db.String(80), nullable=False)  # ej: "LOGIN", "LOGOUT", "RA_SCAN"
    module = db.Column(db.String(50), nullable=True, index=True)  # RESERVATIONS / USERS / INVENTORY / PROFILE
    entity_label = db.Column(db.String(160), nullable=True)  # identificador legible del evento
    description = db.Column(db.Text, nullable=True)    # texto libre

    # Metadata extra (JSON en texto para MVP)
    metadata_json = db.Column(db.Text, nullable=True)

    # Timestamp
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)

    def __repr__(self) -> str:
        return f"<LogbookEvent {self.id} {self.action}>"
