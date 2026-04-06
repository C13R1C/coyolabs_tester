"""bridge missing revision referenced by b7e2f4c9d111

Revision ID: a1c9d7e4b2f0
Revises: 5f72d3a9c1be
Create Date: 2026-03-26 01:20:00.000000

This is an intentionally no-op bridge migration used to restore
Alembic chain continuity for both fresh and existing databases.
"""
from alembic import op


# revision identifiers, used by Alembic.
revision = 'a1c9d7e4b2f0'
down_revision = '5f72d3a9c1be'
branch_labels = None
depends_on = None


def upgrade():
    # no-op: bridge revision only
    pass


def downgrade():
    # no-op: bridge revision only
    pass
