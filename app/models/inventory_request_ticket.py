from app.extensions import db
from app.utils.statuses import InventoryRequestStatus


class InventoryRequestTicket(db.Model):
    __tablename__ = "inventory_request_tickets"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    user = db.relationship("User", backref="inventory_request_tickets")

    request_date = db.Column(db.Date, nullable=False, index=True)
    status = db.Column(db.String(30), nullable=False, default=InventoryRequestStatus.OPEN, index=True)

    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)
    updated_at = db.Column(db.DateTime, onupdate=db.func.now(), nullable=True)

    ready_at = db.Column(db.DateTime, nullable=True)
    closed_at = db.Column(db.DateTime, nullable=True)

    notes = db.Column(db.Text, nullable=True)

    def __repr__(self) -> str:
        return f"<InventoryRequestTicket {self.id} user={self.user_id} date={self.request_date} status={self.status}>"
