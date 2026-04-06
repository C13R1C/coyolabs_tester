from app.extensions import db


class ProfileChangeRequest(db.Model):
    __tablename__ = "profile_change_requests"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    request_type = db.Column(db.String(30), nullable=False)
    requested_phone = db.Column(db.String(30), nullable=True)
    reason = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), nullable=False, default="PENDING")
    reviewed_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)

    user = db.relationship("User", foreign_keys=[user_id], backref="profile_change_requests")
    reviewer = db.relationship("User", foreign_keys=[reviewed_by])

    def __repr__(self) -> str:
        return f"<ProfileChangeRequest {self.id} user={self.user_id} status={self.status}>"
