"""create academic catalog and teacher loads

Revision ID: 6b1e2c3d4f55
Revises: 9f2d7a1c3b44
Create Date: 2026-03-24 04:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '6b1e2c3d4f55'
down_revision = '9f2d7a1c3b44'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'careers',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=160), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )

    op.create_table(
        'subjects',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('career_id', sa.Integer(), nullable=False),
        sa.Column('level', sa.String(length=10), nullable=False),
        sa.Column('quarter', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=160), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['career_id'], ['careers.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('career_id', 'level', 'quarter', 'name', name='uq_subject_catalog')
    )
    op.create_index(op.f('ix_subjects_career_id'), 'subjects', ['career_id'], unique=False)
    op.create_index(op.f('ix_subjects_level'), 'subjects', ['level'], unique=False)

    op.create_table(
        'teacher_academic_loads',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('teacher_id', sa.Integer(), nullable=False),
        sa.Column('subject_id', sa.Integer(), nullable=False),
        sa.Column('group_code', sa.String(length=20), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['subject_id'], ['subjects.id']),
        sa.ForeignKeyConstraint(['teacher_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('teacher_id', 'subject_id', 'group_code', name='uq_teacher_subject_group')
    )
    op.create_index(op.f('ix_teacher_academic_loads_subject_id'), 'teacher_academic_loads', ['subject_id'], unique=False)
    op.create_index(op.f('ix_teacher_academic_loads_teacher_id'), 'teacher_academic_loads', ['teacher_id'], unique=False)

    op.add_column('users', sa.Column('career_id', sa.Integer(), nullable=True))
    op.add_column('users', sa.Column('academic_level', sa.String(length=10), nullable=True))
    op.create_foreign_key('fk_users_career_id', 'users', 'careers', ['career_id'], ['id'])


def downgrade():
    op.drop_constraint('fk_users_career_id', 'users', type_='foreignkey')
    op.drop_column('users', 'academic_level')
    op.drop_column('users', 'career_id')

    op.drop_index(op.f('ix_teacher_academic_loads_teacher_id'), table_name='teacher_academic_loads')
    op.drop_index(op.f('ix_teacher_academic_loads_subject_id'), table_name='teacher_academic_loads')
    op.drop_table('teacher_academic_loads')

    op.drop_index(op.f('ix_subjects_level'), table_name='subjects')
    op.drop_index(op.f('ix_subjects_career_id'), table_name='subjects')
    op.drop_table('subjects')

    op.drop_table('careers')
