"""add persistent pending notifications and admin promotion request

Revision ID: 6aa3c1d9e442
Revises: 1f9b2c4d8e11
Create Date: 2026-04-11 01:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = '6aa3c1d9e442'
down_revision = '1f9b2c4d8e11'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('notifications', sa.Column('event_code', sa.String(length=50), nullable=True))
    op.add_column('notifications', sa.Column('is_persistent', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('notifications', sa.Column('related_user_id', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_notifications_event_code'), 'notifications', ['event_code'], unique=False)
    op.create_index(op.f('ix_notifications_related_user_id'), 'notifications', ['related_user_id'], unique=False)
    op.create_foreign_key('fk_notifications_related_user_id', 'notifications', 'users', ['related_user_id'], ['id'])

    with op.batch_alter_table('critical_action_requests') as batch_op:
        batch_op.drop_constraint('ck_car_action_type', type_='check')
        batch_op.create_check_constraint(
            'ck_car_action_type',
            "action_type in ('DISABLE_USER','ENABLE_USER','BAN_USER','UNBAN_USER','PROMOTE_TO_ADMIN')"
        )


def downgrade():
    with op.batch_alter_table('critical_action_requests') as batch_op:
        batch_op.drop_constraint('ck_car_action_type', type_='check')
        batch_op.create_check_constraint(
            'ck_car_action_type',
            "action_type in ('DISABLE_USER','ENABLE_USER','BAN_USER','UNBAN_USER')"
        )

    op.drop_constraint('fk_notifications_related_user_id', 'notifications', type_='foreignkey')
    op.drop_index(op.f('ix_notifications_related_user_id'), table_name='notifications')
    op.drop_index(op.f('ix_notifications_event_code'), table_name='notifications')
    op.drop_column('notifications', 'related_user_id')
    op.drop_column('notifications', 'is_persistent')
    op.drop_column('notifications', 'event_code')
