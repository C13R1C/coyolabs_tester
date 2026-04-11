"""add root superadmin flag and manual teacher subject

Revision ID: 1f9b2c4d8e11
Revises: 6d4f2a1c8b77, 7b2c4d9e1a11, b4a1f8d2c6e3
Create Date: 2026-04-11 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '1f9b2c4d8e11'
down_revision = ('6d4f2a1c8b77', '7b2c4d9e1a11', 'b4a1f8d2c6e3')
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('is_root_superadmin', sa.Boolean(), nullable=False, server_default=sa.false()))

    op.execute(
        """
        UPDATE users
        SET is_root_superadmin = TRUE
        WHERE id = (
            SELECT id FROM users
            WHERE role = 'SUPERADMIN'
            ORDER BY created_at ASC, id ASC
            LIMIT 1
        )
        """
    )

    op.add_column('teacher_academic_loads', sa.Column('subject_name', sa.String(length=160), nullable=True))

    op.execute(
        """
        UPDATE teacher_academic_loads
        SET subject_name = (
            SELECT subjects.name
            FROM subjects
            WHERE subjects.id = teacher_academic_loads.subject_id
        )
        """
    )

    op.execute(
        """
        UPDATE teacher_academic_loads
        SET subject_name = 'MATERIA SIN NOMBRE'
        WHERE subject_name IS NULL OR TRIM(subject_name) = ''
        """
    )

    with op.batch_alter_table('teacher_academic_loads') as batch_op:
        batch_op.alter_column('subject_name', existing_type=sa.String(length=160), nullable=False)
        batch_op.alter_column('subject_id', existing_type=sa.Integer(), nullable=True)
        batch_op.drop_constraint('uq_teacher_subject_group', type_='unique')
        batch_op.create_unique_constraint('uq_teacher_subject_name_group', ['teacher_id', 'subject_name', 'group_code'])


def downgrade():
    with op.batch_alter_table('teacher_academic_loads') as batch_op:
        batch_op.drop_constraint('uq_teacher_subject_name_group', type_='unique')
        batch_op.create_unique_constraint('uq_teacher_subject_group', ['teacher_id', 'subject_id', 'group_code'])
        batch_op.alter_column('subject_id', existing_type=sa.Integer(), nullable=False)

    op.drop_column('teacher_academic_loads', 'subject_name')
    op.drop_column('users', 'is_root_superadmin')
