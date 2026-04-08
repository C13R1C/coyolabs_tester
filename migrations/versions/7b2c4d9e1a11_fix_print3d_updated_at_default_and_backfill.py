"""fix print3d updated_at default and backfill

Revision ID: 7b2c4d9e1a11
Revises: 3fa529b8f6a0, 5a9d2e3c4b11
Create Date: 2026-04-08 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7b2c4d9e1a11'
down_revision = ('3fa529b8f6a0', '5a9d2e3c4b11')
branch_labels = None
depends_on = None


def upgrade():
    # Backfill legacy NULL values first to avoid NOT NULL violations.
    op.execute(
        """
        UPDATE print3d_jobs
        SET updated_at = COALESCE(created_at, now())
        WHERE updated_at IS NULL
        """
    )

    # Ensure PostgreSQL has a server default and the column is non-nullable.
    op.alter_column(
        'print3d_jobs',
        'updated_at',
        existing_type=sa.DateTime(),
        nullable=False,
        server_default=sa.text('now()'),
    )


def downgrade():
    op.alter_column(
        'print3d_jobs',
        'updated_at',
        existing_type=sa.DateTime(),
        nullable=True,
        server_default=None,
    )
