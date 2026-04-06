"""add signature_ref to reservations

Revision ID: 3c1d5e7f9a21
Revises: 2f6c8a9d4e10
Create Date: 2026-04-06 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3c1d5e7f9a21'
down_revision = '2f6c8a9d4e10'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('reservations', sa.Column('signature_ref', sa.Text(), nullable=True))


def downgrade():
    op.drop_column('reservations', 'signature_ref')
