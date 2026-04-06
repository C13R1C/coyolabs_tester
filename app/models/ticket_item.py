from app.extensions import db
from app.utils.statuses import TicketItemStatus


class TicketItem(db.Model):
    __tablename__ = "ticket_items"

    id = db.Column(db.Integer, primary_key=True)

    ticket_id = db.Column(db.Integer, db.ForeignKey("lab_tickets.id"), nullable=False)
    material_id = db.Column(db.Integer, db.ForeignKey("materials.id"), nullable=False)

    quantity_requested = db.Column(db.Integer, nullable=False, default=0)
    quantity_delivered = db.Column(db.Integer, nullable=False, default=0)
    quantity_returned = db.Column(db.Integer, nullable=False, default=0)

    status = db.Column(db.String(30), nullable=False, default=TicketItemStatus.REQUESTED)
    notes = db.Column(db.Text, nullable=True)

    ticket = db.relationship("LabTicket", backref="items")
    material = db.relationship("Material")

    def __repr__(self) -> str:
        return f"<TicketItem {self.id} ticket={self.ticket_id} material={self.material_id}>"
