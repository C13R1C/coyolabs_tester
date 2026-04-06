"""create critical action requests

Revision ID: c9d3e8a4f221
Revises: b7e2f4c9d111
Create Date: 2026-03-26 00:20:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c9d3e8a4f221'
down_revision = 'b7e2f4c9d111'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'critical_action_requests',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('requester_id', sa.Integer(), nullable=False),
        sa.Column('target_user_id', sa.Integer(), nullable=False),
        sa.Column('action_type', sa.String(length=50), nullable=False),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='PENDING'),
        sa.Column('reviewed_by', sa.Integer(), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['requester_id'], ['users.id']),
        sa.ForeignKeyConstraint(['target_user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['reviewed_by'], ['users.id']),
        sa.CheckConstraint("status in ('PENDING','APPROVED','REJECTED')", name='ck_car_status'),
        sa.CheckConstraint(
            "action_type in ('DISABLE_USER','ENABLE_USER','BAN_USER','UNBAN_USER')",
            name='ck_car_action_type',
        ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_car_requester_id', 'critical_action_requests', ['requester_id'], unique=False)
    op.create_index('ix_car_target_user_id', 'critical_action_requests', ['target_user_id'], unique=False)
    op.create_index('ix_car_status', 'critical_action_requests', ['status'], unique=False)


def downgrade():
    op.drop_index('ix_car_status', table_name='critical_action_requests')
    op.drop_index('ix_car_target_user_id', table_name='critical_action_requests')
    op.drop_index('ix_car_requester_id', table_name='critical_action_requests')
    op.drop_table('critical_action_requests')
