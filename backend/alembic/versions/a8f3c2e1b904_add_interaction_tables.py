"""add interaction tables (comments/likes/favorites/footprints + post counts)

Revision ID: a8f3c2e1b904
Revises: 61edfd32690b
Create Date: 2026-07-08

新增互动层：评论 / 点赞 / 收藏 / 浏览足迹，以及 posts 的三项冗余计数。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a8f3c2e1b904'
down_revision: Union[str, None] = '61edfd32690b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. posts 增加冗余计数字段
    op.add_column('posts', sa.Column('like_count', sa.Integer(), server_default='0', nullable=False))
    op.add_column('posts', sa.Column('comment_count', sa.Integer(), server_default='0', nullable=False))
    op.add_column('posts', sa.Column('view_count', sa.Integer(), server_default='0', nullable=False))

    # 2. 评论
    op.create_table(
        'comments',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('post_id', sa.BigInteger(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('status', sa.SmallInteger(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['post_id'], ['posts.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_comments_post_id'), 'comments', ['post_id'], unique=False)
    op.create_index(op.f('ix_comments_user_id'), 'comments', ['user_id'], unique=False)
    op.create_index(op.f('ix_comments_created_at'), 'comments', ['created_at'], unique=False)

    # 3. 点赞（复合主键防重复）
    op.create_table(
        'likes',
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('post_id', sa.BigInteger(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['post_id'], ['posts.id']),
        sa.PrimaryKeyConstraint('user_id', 'post_id'),
    )

    # 4. 收藏（复合主键防重复）
    op.create_table(
        'favorites',
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('post_id', sa.BigInteger(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['post_id'], ['posts.id']),
        sa.PrimaryKeyConstraint('user_id', 'post_id'),
    )

    # 5. 浏览足迹
    op.create_table(
        'footprints',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('post_id', sa.BigInteger(), nullable=False),
        sa.Column('viewed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['post_id'], ['posts.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_footprints_user_id'), 'footprints', ['user_id'], unique=False)
    op.create_index(op.f('ix_footprints_viewed_at'), 'footprints', ['viewed_at'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_footprints_viewed_at'), table_name='footprints')
    op.drop_index(op.f('ix_footprints_user_id'), table_name='footprints')
    op.drop_table('footprints')

    op.drop_table('favorites')
    op.drop_table('likes')

    op.drop_index(op.f('ix_comments_created_at'), table_name='comments')
    op.drop_index(op.f('ix_comments_user_id'), table_name='comments')
    op.drop_index(op.f('ix_comments_post_id'), table_name='comments')
    op.drop_table('comments')

    op.drop_column('posts', 'view_count')
    op.drop_column('posts', 'comment_count')
    op.drop_column('posts', 'like_count')
