from datetime import datetime
from app.extensions import db

class Print3DJob(db.Model):
    __tablename__ = "print3d_jobs"

    id = db.Column(db.Integer, primary_key=True)

    requester_user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False,
        index=True
    )

    quoted_by_user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=True
    )

    requester_user = db.relationship(
        "User",
        foreign_keys=[requester_user_id],
        backref="print3d_requests"
    )

    quoted_by_user = db.relationship(
        "User",
        foreign_keys=[quoted_by_user_id],
        backref="print3d_quotes"
    )

    title = db.Column(db.String(180), nullable=False)
    description = db.Column(db.Text)

    file_ref = db.Column(db.Text, nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    file_size_bytes = db.Column(db.Integer, nullable=False)

    grams_estimated = db.Column(db.Numeric(10, 2))
    price_per_gram = db.Column(db.Numeric(10, 2))
    total_estimated = db.Column(db.Numeric(10, 2))

    admin_note = db.Column(db.Text)

    ready_notified_at = db.Column(db.DateTime)

    status = db.Column(
        db.String(30),
        nullable=False,
        default="REQUESTED",
        index=True
    )

    created_at = db.Column(
        db.DateTime,
        server_default=db.func.now(),
        nullable=False
    )

    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        server_default=db.func.now(),
        onupdate=datetime.utcnow,
    )

    def __repr__(self):
        return f"<Print3DJob {self.id} requester={self.requester_user_id} status={self.status}>"
