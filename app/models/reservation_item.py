from app.extensions import db


class ReservationItem(db.Model):
    __tablename__ = "reservation_items"

    id = db.Column(db.Integer, primary_key=True)

    reservation_id = db.Column(
        db.Integer,
        db.ForeignKey("reservations.id"),
        nullable=False
    )

    material_id = db.Column(
        db.Integer,
        db.ForeignKey("materials.id"),
        nullable=False
    )

    quantity_requested = db.Column(db.Integer, nullable=False, default=1)
    notes = db.Column(db.Text, nullable=True)

    reservation = db.relationship("Reservation", backref="items")
    material = db.relationship("Material")