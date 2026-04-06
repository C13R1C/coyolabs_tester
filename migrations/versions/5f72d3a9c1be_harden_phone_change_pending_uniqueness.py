"""harden phone-change pending uniqueness

Revision ID: 5f72d3a9c1be
Revises: 31f8a2c4d9aa
Create Date: 2026-03-26 15:10:00.000000

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = '5f72d3a9c1be'
down_revision = '31f8a2c4d9aa'
branch_labels = None
depends_on = None


INDEX_NAME = 'uq_pcr_pending_phone_change_per_user'


def upgrade():
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect in {'postgresql', 'sqlite'}:
        op.execute(
            f"CREATE UNIQUE INDEX {INDEX_NAME} "
            "ON profile_change_requests (user_id) "
            "WHERE request_type = 'PHONE_CHANGE' AND status = 'PENDING'"
        )


def downgrade():
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect in {'postgresql', 'sqlite'}:
        op.execute(f"DROP INDEX IF EXISTS {INDEX_NAME}")
