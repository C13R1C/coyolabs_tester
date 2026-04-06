"""create inventory request tables

Revision ID: c41a6b2c9d10
Revises: 4a7b2d1f9c11
Create Date: 2026-03-24 02:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c41a6b2c9d10'
down_revision = '4a7b2d1f9c11'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'inventory_request_tickets',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('request_date', sa.Date(), nullable=False),
        sa.Column('status', sa.String(length=30), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('ready_at', sa.DateTime(), nullable=True),
        sa.Column('closed_at', sa.DateTime(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_inventory_request_tickets_request_date'), 'inventory_request_tickets', ['request_date'], unique=False)
    op.create_index(op.f('ix_inventory_request_tickets_status'), 'inventory_request_tickets', ['status'], unique=False)
    op.create_index(op.f('ix_inventory_request_tickets_user_id'), 'inventory_request_tickets', ['user_id'], unique=False)

    op.create_table(
        'inventory_request_items',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('ticket_id', sa.Integer(), nullable=False),
        sa.Column('material_id', sa.Integer(), nullable=False),
        sa.Column('quantity_requested', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['material_id'], ['materials.id']),
        sa.ForeignKeyConstraint(['ticket_id'], ['inventory_request_tickets.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('ticket_id', 'material_id', name='uq_inventory_request_item_ticket_material')
    )


def downgrade():
    op.drop_table('inventory_request_items')
    op.drop_index(op.f('ix_inventory_request_tickets_user_id'), table_name='inventory_request_tickets')
    op.drop_index(op.f('ix_inventory_request_tickets_status'), table_name='inventory_request_tickets')
    op.drop_index(op.f('ix_inventory_request_tickets_request_date'), table_name='inventory_request_tickets')
    op.drop_table('inventory_request_tickets')
