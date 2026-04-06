"""add module and entity label to logbook

Revision ID: d1a4b6c8e902
Revises: c9d3e8a4f221
Create Date: 2026-03-26 00:35:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd1a4b6c8e902'
down_revision = 'c9d3e8a4f221'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('logbook_events', schema=None) as batch_op:
        batch_op.add_column(sa.Column('module', sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column('entity_label', sa.String(length=160), nullable=True))
        batch_op.create_index('ix_logbook_events_module', ['module'], unique=False)


def downgrade():
    with op.batch_alter_table('logbook_events', schema=None) as batch_op:
        batch_op.drop_index('ix_logbook_events_module')
        batch_op.drop_column('entity_label')
        batch_op.drop_column('module')
