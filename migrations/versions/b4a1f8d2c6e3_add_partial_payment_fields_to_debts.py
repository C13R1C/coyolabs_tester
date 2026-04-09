"""add partial payment fields to debts

Revision ID: b4a1f8d2c6e3
Revises: 9c2f4a7d11b2
Create Date: 2026-04-09 00:00:01.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'b4a1f8d2c6e3'
down_revision = '9c2f4a7d11b2'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('debts', sa.Column('original_amount', sa.Numeric(10, 2), nullable=True))
    op.add_column('debts', sa.Column('remaining_amount', sa.Numeric(10, 2), nullable=True))

    op.execute("""
        UPDATE debts
        SET
            original_amount = COALESCE(amount, 0),
            remaining_amount = CASE
                WHEN UPPER(COALESCE(status, '')) = 'PAID' THEN 0
                ELSE COALESCE(amount, 0)
            END
        WHERE original_amount IS NULL OR remaining_amount IS NULL
    """)


def downgrade():
    op.drop_column('debts', 'remaining_amount')
    op.drop_column('debts', 'original_amount')
