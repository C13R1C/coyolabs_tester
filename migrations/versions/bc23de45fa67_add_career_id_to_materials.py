"""add career_id to materials

Revision ID: bc23de45fa67
Revises: ab12cd34ef56
Create Date: 2026-04-02 00:30:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "bc23de45fa67"
down_revision = "ab12cd34ef56"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("materials", sa.Column("career_id", sa.Integer(), nullable=True))
    op.create_index("ix_materials_career_id", "materials", ["career_id"], unique=False)
    op.create_foreign_key(
        "fk_materials_career_id_careers",
        "materials",
        "careers",
        ["career_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_materials_career_id_careers", "materials", type_="foreignkey")
    op.drop_index("ix_materials_career_id", table_name="materials")
    op.drop_column("materials", "career_id")
