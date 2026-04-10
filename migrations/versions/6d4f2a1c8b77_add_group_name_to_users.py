"""add group_name to users

Revision ID: 6d4f2a1c8b77
Revises: c9d3e8a4f221
Create Date: 2026-04-10 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '6d4f2a1c8b77'
down_revision = 'c9d3e8a4f221'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('group_name', sa.String(length=80), nullable=True))


def downgrade():
    op.drop_column('users', 'group_name')
