"""add category to materials

Revision ID: ab12cd34ef56
Revises: 8f4c2a1b7d90
Create Date: 2026-04-02 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "ab12cd34ef56"
down_revision = "8f4c2a1b7d90"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("materials", sa.Column("category", sa.String(length=80), nullable=True))
    op.create_index("ix_materials_category", "materials", ["category"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_materials_category", table_name="materials")
    op.drop_column("materials", "category")
