from app.extensions import db
from sqlalchemy.sql import func

class Notification(db.Model):
    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    related_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    title = db.Column(db.String(255), nullable=False)
    message = db.Column(db.Text, nullable=False)
    link = db.Column(db.String(255))
    event_code = db.Column(db.String(80), nullable=True, index=True)
    is_persistent = db.Column(db.Boolean, nullable=False, default=False)
    is_read = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, server_default=func.now())

    user = db.relationship(
        "User",
        foreign_keys=[user_id],
        back_populates="notifications"
    )

    related_user = db.relationship(
        "User",
        foreign_keys=[related_user_id]
    )

    def __repr__(self) -> str:
        return f"<Notification {self.id} user={self.user_id} read={self.is_read}>"
