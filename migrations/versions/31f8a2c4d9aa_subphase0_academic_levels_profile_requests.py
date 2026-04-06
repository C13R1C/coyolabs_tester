"""subphase0 academic levels and profile change requests

Revision ID: 31f8a2c4d9aa
Revises: 6b1e2c3d4f55
Create Date: 2026-03-26 12:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '31f8a2c4d9aa'
down_revision = '6b1e2c3d4f55'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'academic_levels',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('code', sa.String(length=20), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code', name='uq_academic_levels_code'),
        sa.UniqueConstraint('name', name='uq_academic_levels_name'),
    )
    op.create_index('ix_academic_levels_is_active', 'academic_levels', ['is_active'], unique=False)

    op.create_table(
        'profile_change_requests',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('request_type', sa.String(length=30), nullable=False),
        sa.Column('requested_phone', sa.String(length=30), nullable=True),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='PENDING'),
        sa.Column('reviewed_by', sa.Integer(), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint("status IN ('PENDING', 'APPROVED', 'REJECTED')", name='ck_profile_change_requests_status'),
        sa.CheckConstraint("request_type IN ('PHONE_CHANGE', 'PROFILE_CHANGE')", name='ck_profile_change_requests_type'),
        sa.ForeignKeyConstraint(['reviewed_by'], ['users.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_profile_change_requests_user_id', 'profile_change_requests', ['user_id'], unique=False)
    op.create_index('ix_profile_change_requests_status', 'profile_change_requests', ['status'], unique=False)

    op.add_column('users', sa.Column('academic_level_id', sa.Integer(), nullable=True))
    op.add_column('users', sa.Column('profile_data_confirmed', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('users', sa.Column('profile_confirmed_at', sa.DateTime(), nullable=True))
    op.create_foreign_key('fk_users_academic_level_id', 'users', 'academic_levels', ['academic_level_id'], ['id'])
    op.create_index('ix_users_academic_level_id', 'users', ['academic_level_id'], unique=False)
    op.create_index('ix_users_career_level', 'users', ['career_id', 'academic_level_id'], unique=False)

    op.add_column('subjects', sa.Column('academic_level_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_subjects_academic_level_id', 'subjects', 'academic_levels', ['academic_level_id'], ['id'])
    op.create_index('ix_subjects_academic_level_id', 'subjects', ['academic_level_id'], unique=False)

    op.add_column('reservations', sa.Column('subject_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_reservations_subject_id', 'reservations', 'subjects', ['subject_id'], ['id'])
    op.create_index('ix_reservations_subject_id', 'reservations', ['subject_id'], unique=False)
    op.create_index('ix_reservations_date_room_status', 'reservations', ['date', 'room', 'status'], unique=False)


def downgrade():
    op.drop_index('ix_reservations_date_room_status', table_name='reservations')
    op.drop_index('ix_reservations_subject_id', table_name='reservations')
    op.drop_constraint('fk_reservations_subject_id', 'reservations', type_='foreignkey')
    op.drop_column('reservations', 'subject_id')

    op.drop_index('ix_subjects_academic_level_id', table_name='subjects')
    op.drop_constraint('fk_subjects_academic_level_id', 'subjects', type_='foreignkey')
    op.drop_column('subjects', 'academic_level_id')

    op.drop_index('ix_users_career_level', table_name='users')
    op.drop_index('ix_users_academic_level_id', table_name='users')
    op.drop_constraint('fk_users_academic_level_id', 'users', type_='foreignkey')
    op.drop_column('users', 'profile_confirmed_at')
    op.drop_column('users', 'profile_data_confirmed')
    op.drop_column('users', 'academic_level_id')

    op.drop_index('ix_profile_change_requests_status', table_name='profile_change_requests')
    op.drop_index('ix_profile_change_requests_user_id', table_name='profile_change_requests')
    op.drop_table('profile_change_requests')

    op.drop_index('ix_academic_levels_is_active', table_name='academic_levels')
    op.drop_table('academic_levels')
