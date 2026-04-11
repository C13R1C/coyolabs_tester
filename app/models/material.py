from app.extensions import db


class Material(db.Model):
    __tablename__ = "materials"

    id = db.Column(db.Integer, primary_key=True)

    # Relación a laboratorio
    lab_id = db.Column(db.Integer, db.ForeignKey("labs.id"), nullable=False)
    lab = db.relationship("Lab", backref="materials")
    career_id = db.Column(db.Integer, db.ForeignKey("careers.id"), nullable=True)
    career = db.relationship("Career", backref="materials")

    # Datos base (lo que aparece en Excel)
    name = db.Column(db.Text, nullable=False)             # Equipo / Material
    category = db.Column(db.String(80), nullable=True, index=True)  # Categoría operativa
    location = db.Column(db.Text, nullable=True)          # Ubicación/Estante/Gabinete
    status = db.Column(db.Text, nullable=True)            # Estado

    # Piezas: guardamos el texto original + un número si se puede parsear
    pieces_text = db.Column(db.Text, nullable=True)        # ej: "20/20", "5", "N/A"
    pieces_qty = db.Column(db.Integer, nullable=True)            # ej: 20 (si se puede)

    # Campos que a veces vienen en Excel
    brand = db.Column(db.Text, nullable=True)
    model = db.Column(db.Text, nullable=True)
    code = db.Column(db.Text, nullable=True)              # códigos tipo "D1, D2..."
    serial = db.Column(db.Text, nullable=True)

    # Evidencia / tutorial / notas
    image_ref = db.Column(db.Text, nullable=True)         # path/URL o referencia
    image_url = db.Column(db.Text, nullable=True)
    tutorial_url = db.Column(db.Text, nullable=True)
    notes = db.Column(db.Text, nullable=True)

    # Trazabilidad (muy importante para “subir tal cual”)
    source_file = db.Column(db.Text, nullable=True)
    source_sheet = db.Column(db.Text, nullable=True)
    ####
    source_row = db.Column(db.Integer, nullable=True)

    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)
    updated_at = db.Column(db.DateTime, onupdate=db.func.now(), nullable=True)

    def __repr__(self) -> str:
        return f"<Material {self.id} {self.name}>"
