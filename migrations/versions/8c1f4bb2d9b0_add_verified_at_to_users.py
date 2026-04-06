"""add verified_at to users

Revision ID: 8c1f4bb2d9b0
Revises: e7a22c9056e4
Create Date: 2026-03-24 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8c1f4bb2d9b0'
down_revision = 'e7a22c9056e4'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('verified_at', sa.DateTime(), nullable=True))


def downgrade():
    op.drop_column('users', 'verified_at')
