"""add case_code to debts

Revision ID: 2a6d4e8f1b3c
Revises: b4a1f8d2c6e3
Create Date: 2026-04-09 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "2a6d4e8f1b3c"
down_revision = "b4a1f8d2c6e3"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("debts", sa.Column("case_code", sa.String(length=36), nullable=True))
    op.create_index("ix_debts_case_code", "debts", ["case_code"], unique=False)


def downgrade():
    op.drop_index("ix_debts_case_code", table_name="debts")
    op.drop_column("debts", "case_code")
