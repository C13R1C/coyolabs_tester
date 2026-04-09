"""add delivery/return qty fields to inventory request items

Revision ID: 9c2f4a7d11b2
Revises: ce21f9a4b6d3
Create Date: 2026-04-09 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9c2f4a7d11b2'
down_revision = 'ce21f9a4b6d3'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('inventory_request_items', sa.Column('quantity_delivered', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('inventory_request_items', sa.Column('quantity_returned', sa.Integer(), nullable=False, server_default='0'))
    op.alter_column('inventory_request_items', 'quantity_delivered', server_default=None)
    op.alter_column('inventory_request_items', 'quantity_returned', server_default=None)


def downgrade():
    op.drop_column('inventory_request_items', 'quantity_returned')
    op.drop_column('inventory_request_items', 'quantity_delivered')
