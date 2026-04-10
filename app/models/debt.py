from app.extensions import db
from app.utils.statuses import DebtStatus


class Debt(db.Model):
    __tablename__ = "debts"

    id = db.Column(db.Integer, primary_key=True)

    # Usuario que debe (normalmente STUDENT)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    user = db.relationship("User", backref="debts")

    # Material relacionado (opcional: algunos adeudos pueden ser “genéricos”)
    material_id = db.Column(db.Integer, db.ForeignKey("materials.id"), nullable=True)
    material = db.relationship("Material", backref="debts")
    ticket_id = db.Column(db.Integer, db.ForeignKey("lab_tickets.id"), nullable=True, index=True)
    ticket = db.relationship("LabTicket", back_populates="debts")
    case_code = db.Column(db.String(36), nullable=True, index=True)

    # Estado del adeudo
    status = db.Column(db.String(20), nullable=False, default=DebtStatus.PENDING)

    # Motivo / detalle
    reason = db.Column(db.Text, nullable=True)

    # Monto (si aplica)
    amount = db.Column(db.Numeric(10, 2), nullable=True)
    original_amount = db.Column(db.Numeric(10, 2), nullable=True)
    remaining_amount = db.Column(db.Numeric(10, 2), nullable=True)

    # Fechas
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)
    closed_at = db.Column(db.DateTime, nullable=True)

    def __repr__(self) -> str:
        return f"<Debt {self.id} user={self.user_id} status={self.status}>"
