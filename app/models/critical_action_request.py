from app.extensions import db


class CriticalActionRequest(db.Model):
    __tablename__ = "critical_action_requests"

    id = db.Column(db.Integer, primary_key=True)

    requester_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    target_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)

    action_type = db.Column(db.String(50), nullable=False)  # DISABLE_USER / ENABLE_USER / BAN_USER / UNBAN_USER / PROMOTE_TO_ADMIN
    reason = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), nullable=False, default="PENDING", index=True)  # PENDING/APPROVED/REJECTED

    reviewed_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)

    requester = db.relationship("User", foreign_keys=[requester_id], backref="critical_action_requests_created")
    target_user = db.relationship("User", foreign_keys=[target_user_id], backref="critical_action_requests_target")
    reviewer = db.relationship("User", foreign_keys=[reviewed_by], backref="critical_action_requests_reviewed")

    __table_args__ = (
        db.CheckConstraint("status in ('PENDING','APPROVED','REJECTED')", name="ck_car_status"),
        db.CheckConstraint(
            "action_type in ('DISABLE_USER','ENABLE_USER','BAN_USER','UNBAN_USER','PROMOTE_TO_ADMIN')",
            name="ck_car_action_type",
        ),
    )

    def __repr__(self) -> str:
        return f"<CriticalActionRequest {self.id} {self.action_type} {self.status}>"
