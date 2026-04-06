"""add ticket_id fk to debts

Revision ID: 2f6c8a9d4e10
Revises: 8f4c2a1b7d90
Create Date: 2026-04-03 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
import re


# revision identifiers, used by Alembic.
revision = '2f6c8a9d4e10'
down_revision = '8f4c2a1b7d90'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('debts', sa.Column('ticket_id', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_debts_ticket_id'), 'debts', ['ticket_id'], unique=False)
    op.create_foreign_key('fk_debts_ticket_id_lab_tickets', 'debts', 'lab_tickets', ['ticket_id'], ['id'])

    bind = op.get_bind()
    debts = sa.table(
        'debts',
        sa.column('id', sa.Integer()),
        sa.column('reason', sa.Text()),
        sa.column('ticket_id', sa.Integer()),
    )
    lab_tickets = sa.table('lab_tickets', sa.column('id', sa.Integer()))

    rows = bind.execute(sa.select(debts.c.id, debts.c.reason).where(debts.c.reason.is_not(None))).fetchall()
    for debt_id, reason in rows:
        match = re.search(r'ticket\s*#(\d+)', reason, flags=re.IGNORECASE)
        if not match:
            continue

        ticket_id = int(match.group(1))
        ticket_exists = bind.execute(sa.select(lab_tickets.c.id).where(lab_tickets.c.id == ticket_id)).scalar_one_or_none()
        if ticket_exists is None:
            continue

        bind.execute(
            debts.update().where(debts.c.id == debt_id).values(ticket_id=ticket_id)
        )


def downgrade():
    op.drop_constraint('fk_debts_ticket_id_lab_tickets', 'debts', type_='foreignkey')
    op.drop_index(op.f('ix_debts_ticket_id'), table_name='debts')
    op.drop_column('debts', 'ticket_id')
