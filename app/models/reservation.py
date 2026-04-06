from app.extensions import db
from app.utils.statuses import ReservationStatus


class Reservation(db.Model):
    __tablename__ = "reservations"

    id = db.Column(db.Integer, primary_key=True)

    # solicitante
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    user = db.relationship("User", backref="reservations")

    # datos de reserva
    room = db.Column(db.String(80), nullable=False)         # ej. "Lab Redes", "Salon 3"
    date = db.Column(db.Date, nullable=False)              # fecha
    start_time = db.Column(db.Time, nullable=False)        # hora inicio
    end_time = db.Column(db.Time, nullable=False)          # hora fin
    purpose = db.Column(db.Text, nullable=True)

    # workflow
    status = db.Column(db.String(20), nullable=False, default=ReservationStatus.PENDING)
    admin_note = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)
    updated_at = db.Column(db.DateTime, onupdate=db.func.now())

    group_name = db.Column(db.String(50), nullable=False)     # ej. "3A", "2B"
    teacher_name = db.Column(db.String(120), nullable=False)  # nombre del profe
    subject = db.Column(db.String(120), nullable=False)       # materia
    subject_id = db.Column(db.Integer, db.ForeignKey("subjects.id"), nullable=True, index=True)
    signed = db.Column(db.Boolean, nullable=False, default=False)  # "firma" digital simple
    signature_ref = db.Column(db.Text, nullable=True)  # referencia a evidencia de firma (imagen)

    exit_time = db.Column(db.Time, nullable=True)             # hora salida real
    teacher_comments = db.Column(db.Text, nullable=True)      # comentarios al salir
    subject_rel = db.relationship("Subject", foreign_keys=[subject_id])


    def __repr__(self) -> str:
        return f"<Reservation {self.id} {self.room} {self.date} {self.status}>"
