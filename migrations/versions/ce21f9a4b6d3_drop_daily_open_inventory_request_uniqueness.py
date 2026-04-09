"""drop daily-open uniqueness for inventory requests

Revision ID: ce21f9a4b6d3
Revises: b7e2f4c9d111
Create Date: 2026-04-09 10:30:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "ce21f9a4b6d3"
down_revision = "b7e2f4c9d111"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    indexes = {idx.get("name") for idx in inspector.get_indexes("inventory_request_tickets")}
    if "uq_inventory_open_ticket_per_user_day" in indexes:
        op.drop_index("uq_inventory_open_ticket_per_user_day", table_name="inventory_request_tickets")


def downgrade():
    bind = op.get_bind()
    dialect = bind.dialect.name
    if dialect in {"postgresql", "sqlite"}:
        op.create_index(
            "uq_inventory_open_ticket_per_user_day",
            "inventory_request_tickets",
            ["user_id", "request_date"],
            unique=True,
            postgresql_where=sa.text("status = 'OPEN'"),
            sqlite_where=sa.text("status = 'OPEN'"),
        )
