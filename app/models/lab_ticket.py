from app.extensions import db
from app.utils.statuses import LabTicketStatus


class LabTicket(db.Model):
    __tablename__ = "lab_tickets"

    id = db.Column(db.Integer, primary_key=True)

    reservation_id = db.Column(db.Integer, db.ForeignKey("reservations.id"), nullable=True)
    owner_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    room = db.Column(db.String(120), nullable=True)
    date = db.Column(db.Date, nullable=True)

    status = db.Column(db.String(30), nullable=False, default=LabTicketStatus.OPEN)

    opened_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)
    closed_at = db.Column(db.DateTime, nullable=True)

    opened_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    closed_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    notes = db.Column(db.Text, nullable=True)

    reservation = db.relationship("Reservation", backref="lab_tickets", foreign_keys=[reservation_id])
    owner_user = db.relationship("User", foreign_keys=[owner_user_id])
    opened_by_user = db.relationship("User", foreign_keys=[opened_by_user_id])
    closed_by_user = db.relationship("User", foreign_keys=[closed_by_user_id])
    debts = db.relationship("Debt", back_populates="ticket")

    def __repr__(self) -> str:
        return f"<LabTicket {self.id} {self.status}>"
