from app.extensions import db


class Subject(db.Model):
    __tablename__ = "subjects"

    id = db.Column(db.Integer, primary_key=True)
    career_id = db.Column(db.Integer, db.ForeignKey("careers.id"), nullable=False, index=True)
    level = db.Column(db.String(10), nullable=False, index=True)  # TSU / ING
    academic_level_id = db.Column(db.Integer, db.ForeignKey("academic_levels.id"), nullable=True, index=True)
    quarter = db.Column(db.Integer, nullable=False)
    name = db.Column(db.String(160), nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)

    career = db.relationship("Career", backref="subjects")
    academic_level = db.relationship("AcademicLevel", backref="subjects")

    __table_args__ = (
        db.UniqueConstraint("career_id", "level", "quarter", "name", name="uq_subject_catalog"),
    )

    def __repr__(self) -> str:
        return f"<Subject {self.id} {self.name}>"
