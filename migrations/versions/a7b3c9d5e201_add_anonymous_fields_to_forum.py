"""add anonymous fields to forum

Revision ID: a7b3c9d5e201
Revises: f2c4a8b9d101
Create Date: 2026-03-26 19:10:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a7b3c9d5e201'
down_revision = 'f2c4a8b9d101'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('forum_posts', sa.Column('is_anonymous', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('forum_comments', sa.Column('is_anonymous', sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade():
    op.drop_column('forum_comments', 'is_anonymous')
    op.drop_column('forum_posts', 'is_anonymous')
