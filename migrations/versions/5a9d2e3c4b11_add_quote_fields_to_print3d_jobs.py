"""add quote fields to print3d_jobs

Revision ID: 5a9d2e3c4b11
Revises: 4f8e1c2a9b77
Create Date: 2026-04-06 00:00:02.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5a9d2e3c4b11'
down_revision = '4f8e1c2a9b77'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('print3d_jobs', sa.Column('grams_estimated', sa.Numeric(precision=10, scale=2), nullable=True))
    op.add_column('print3d_jobs', sa.Column('price_per_gram', sa.Numeric(precision=10, scale=2), nullable=True))
    op.add_column('print3d_jobs', sa.Column('total_estimated', sa.Numeric(precision=10, scale=2), nullable=True))


def downgrade():
    op.drop_column('print3d_jobs', 'total_estimated')
    op.drop_column('print3d_jobs', 'price_per_gram')
    op.drop_column('print3d_jobs', 'grams_estimated')
