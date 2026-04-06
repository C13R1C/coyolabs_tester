"""add profile fields to users

Revision ID: 4a7b2d1f9c11
Revises: 8c1f4bb2d9b0
Create Date: 2026-03-24 00:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4a7b2d1f9c11'
down_revision = '8c1f4bb2d9b0'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('profile_completed', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('users', sa.Column('full_name', sa.String(length=150), nullable=True))
    op.add_column('users', sa.Column('matricula', sa.String(length=30), nullable=True))
    op.add_column('users', sa.Column('career', sa.String(length=120), nullable=True))
    op.add_column('users', sa.Column('career_year', sa.Integer(), nullable=True))
    op.add_column('users', sa.Column('phone', sa.String(length=30), nullable=True))
    op.add_column('users', sa.Column('professor_subjects', sa.Text(), nullable=True))


def downgrade():
    op.drop_column('users', 'professor_subjects')
    op.drop_column('users', 'phone')
    op.drop_column('users', 'career_year')
    op.drop_column('users', 'career')
    op.drop_column('users', 'matricula')
    op.drop_column('users', 'full_name')
    op.drop_column('users', 'profile_completed')
