from app.extensions import db


class TeacherAcademicLoad(db.Model):
    __tablename__ = "teacher_academic_loads"

    id = db.Column(db.Integer, primary_key=True)

    teacher_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    subject_id = db.Column(db.Integer, db.ForeignKey("subjects.id"), nullable=True, index=True)
    subject_name = db.Column(db.String(160), nullable=False)
    group_code = db.Column(db.String(20), nullable=False)

    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)

    teacher = db.relationship("User", backref="teaching_loads", foreign_keys=[teacher_id])
    subject = db.relationship("Subject", backref="teacher_loads", foreign_keys=[subject_id])

    __table_args__ = (
        db.UniqueConstraint("teacher_id", "subject_name", "group_code", name="uq_teacher_subject_name_group"),
    )

    def __repr__(self) -> str:
        return f"<TeacherAcademicLoad {self.id} teacher={self.teacher_id} subject={self.subject_id} group={self.group_code}>"
