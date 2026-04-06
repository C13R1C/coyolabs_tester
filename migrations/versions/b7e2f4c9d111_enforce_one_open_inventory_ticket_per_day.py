"""enforce one open inventory ticket per user per day

Revision ID: b7e2f4c9d111
Revises: a1c9d7e4b2f0
Create Date: 2026-03-26 00:10:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b7e2f4c9d111'
down_revision = 'a1c9d7e4b2f0'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect in {"postgresql", "sqlite"}:
        op.create_index(
            'uq_inventory_open_ticket_per_user_day',
            'inventory_request_tickets',
            ['user_id', 'request_date'],
            unique=True,
            postgresql_where=sa.text("status = 'OPEN'"),
            sqlite_where=sa.text("status = 'OPEN'"),
        )


def downgrade():
    bind = op.get_bind()
    dialect = bind.dialect.name
    if dialect in {"postgresql", "sqlite"}:
        op.drop_index('uq_inventory_open_ticket_per_user_day', table_name='inventory_request_tickets')
