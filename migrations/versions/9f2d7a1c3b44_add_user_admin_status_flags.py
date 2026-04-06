"""add user admin status flags

Revision ID: 9f2d7a1c3b44
Revises: c41a6b2c9d10
Create Date: 2026-03-24 03:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9f2d7a1c3b44'
down_revision = 'c41a6b2c9d10'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column('users', sa.Column('is_banned', sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade():
    op.drop_column('users', 'is_banned')
    op.drop_column('users', 'is_active')
