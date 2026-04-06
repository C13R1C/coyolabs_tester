"""create forum posts and comments

Revision ID: f2c4a8b9d101
Revises: d1a4b6c8e902
Create Date: 2026-03-26 18:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f2c4a8b9d101'
down_revision = 'd1a4b6c8e902'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'forum_posts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('author_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=180), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('category', sa.String(length=30), nullable=False, server_default='GENERAL'),
        sa.Column('is_hidden', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('hidden_by', sa.Integer(), nullable=True),
        sa.Column('hidden_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['author_id'], ['users.id']),
        sa.ForeignKeyConstraint(['hidden_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_forum_posts_author_id', 'forum_posts', ['author_id'], unique=False)
    op.create_index('ix_forum_posts_created_at', 'forum_posts', ['created_at'], unique=False)
    op.create_index('ix_forum_posts_category', 'forum_posts', ['category'], unique=False)

    op.create_table(
        'forum_comments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('post_id', sa.Integer(), nullable=False),
        sa.Column('author_id', sa.Integer(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('is_hidden', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('hidden_by', sa.Integer(), nullable=True),
        sa.Column('hidden_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['post_id'], ['forum_posts.id']),
        sa.ForeignKeyConstraint(['author_id'], ['users.id']),
        sa.ForeignKeyConstraint(['hidden_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_forum_comments_post_id', 'forum_comments', ['post_id'], unique=False)
    op.create_index('ix_forum_comments_author_id', 'forum_comments', ['author_id'], unique=False)
    op.create_index('ix_forum_comments_created_at', 'forum_comments', ['created_at'], unique=False)


def downgrade():
    op.drop_index('ix_forum_comments_created_at', table_name='forum_comments')
    op.drop_index('ix_forum_comments_author_id', table_name='forum_comments')
    op.drop_index('ix_forum_comments_post_id', table_name='forum_comments')
    op.drop_table('forum_comments')

    op.drop_index('ix_forum_posts_category', table_name='forum_posts')
    op.drop_index('ix_forum_posts_created_at', table_name='forum_posts')
    op.drop_index('ix_forum_posts_author_id', table_name='forum_posts')
    op.drop_table('forum_posts')
