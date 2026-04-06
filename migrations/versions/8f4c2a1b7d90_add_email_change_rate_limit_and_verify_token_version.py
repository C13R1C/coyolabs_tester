"""add email change rate limit and verify token version

Revision ID: 8f4c2a1b7d90
Revises: a7b3c9d5e201
Create Date: 2026-03-27 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8f4c2a1b7d90'
down_revision = 'a7b3c9d5e201'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('verify_token_version', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('users', sa.Column('email_change_count', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('users', sa.Column('email_change_window_started_at', sa.DateTime(), nullable=True))


def downgrade():
    op.drop_column('users', 'email_change_window_started_at')
    op.drop_column('users', 'email_change_count')
    op.drop_column('users', 'verify_token_version')
