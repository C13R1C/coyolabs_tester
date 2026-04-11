from app.extensions import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)

    email = db.Column(db.String(120), unique=True, nullable=False)

    password_hash = db.Column(db.String(255), nullable=False)

    role = db.Column(db.String(20), nullable=False, default="STUDENT")
    is_root_superadmin = db.Column(db.Boolean, nullable=False, default=False)

    is_verified = db.Column(db.Boolean, nullable=False, default=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    is_banned = db.Column(db.Boolean, nullable=False, default=False)
    verified_at = db.Column(db.DateTime, nullable=True)
    verify_token_version = db.Column(db.Integer, nullable=False, default=0)
    email_change_count = db.Column(db.Integer, nullable=False, default=0)
    email_change_window_started_at = db.Column(db.DateTime, nullable=True)
    profile_completed = db.Column(db.Boolean, nullable=False, default=False)
    career_id = db.Column(db.Integer, db.ForeignKey("careers.id"), nullable=True)
    academic_level = db.Column(db.String(10), nullable=True)  # TSU / ING
    academic_level_id = db.Column(db.Integer, db.ForeignKey("academic_levels.id"), nullable=True)
    profile_data_confirmed = db.Column(db.Boolean, nullable=False, default=False)
    profile_confirmed_at = db.Column(db.DateTime, nullable=True)
    full_name = db.Column(db.String(150), nullable=True)
    matricula = db.Column(db.String(30), nullable=True)
    career = db.Column(db.String(120), nullable=True)
    career_year = db.Column(db.Integer, nullable=True)
    phone = db.Column(db.String(30), nullable=True)
    group_name = db.Column(db.String(80), nullable=True)
    professor_subjects = db.Column(db.Text, nullable=True)
    career_rel = db.relationship("Career", backref="users", foreign_keys=[career_id])
    academic_level_rel = db.relationship("AcademicLevel", backref="users", foreign_keys=[academic_level_id])
    notifications = db.relationship(
    "Notification",
    foreign_keys="Notification.user_id",
    back_populates="user",
    lazy="dynamic"
)

    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)
