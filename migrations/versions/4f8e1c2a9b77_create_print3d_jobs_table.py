"""create print3d_jobs table

Revision ID: 4f8e1c2a9b77
Revises: 3c1d5e7f9a21
Create Date: 2026-04-06 00:00:01.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4f8e1c2a9b77'
down_revision = '3c1d5e7f9a21'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'print3d_jobs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('requester_user_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=180), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('file_ref', sa.Text(), nullable=False),
        sa.Column('original_filename', sa.String(length=255), nullable=False),
        sa.Column('file_size_bytes', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=30), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['requester_user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_print3d_jobs_requester_user_id'), 'print3d_jobs', ['requester_user_id'], unique=False)
    op.create_index(op.f('ix_print3d_jobs_status'), 'print3d_jobs', ['status'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_print3d_jobs_status'), table_name='print3d_jobs')
    op.drop_index(op.f('ix_print3d_jobs_requester_user_id'), table_name='print3d_jobs')
    op.drop_table('print3d_jobs')
