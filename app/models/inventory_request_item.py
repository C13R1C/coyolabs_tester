from app.extensions import db


class InventoryRequestItem(db.Model):
    __tablename__ = "inventory_request_items"

    id = db.Column(db.Integer, primary_key=True)

    ticket_id = db.Column(db.Integer, db.ForeignKey("inventory_request_tickets.id"), nullable=False)
    material_id = db.Column(db.Integer, db.ForeignKey("materials.id"), nullable=False)

    quantity_requested = db.Column(db.Integer, nullable=False, default=0)
    quantity_delivered = db.Column(db.Integer, nullable=False, default=0)
    quantity_returned = db.Column(db.Integer, nullable=False, default=0)

    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)

    ticket = db.relationship("InventoryRequestTicket", backref="items")
    material = db.relationship("Material")

    __table_args__ = (
        db.UniqueConstraint("ticket_id", "material_id", name="uq_inventory_request_item_ticket_material"),
    )

    def __repr__(self) -> str:
        return f"<InventoryRequestItem {self.id} ticket={self.ticket_id} material={self.material_id}>"
