"""add banners table + post pin fields + report handler fields

Revision ID: a1b2c3d4e607
Revises: f7a9c2d4e506
Create Date: 2026-08-30
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a1b2c3d4e607'
down_revision: Union[str, None] = 'f7a9c2d4e506'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 首页轮播广告位（独立运营表）
    op.create_table(
        'banners',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('title', sa.String(50), nullable=False),
        sa.Column('desc', sa.String(100), nullable=True),
        sa.Column('tag', sa.String(10), nullable=True),
        sa.Column('image_url', sa.String(500), nullable=True),
        sa.Column('link_url', sa.String(500), nullable=True),
        sa.Column('post_id', sa.BigInteger(), nullable=True),
        sa.Column('sort', sa.Integer(), nullable=True),
        sa.Column('status', sa.SmallInteger(), nullable=True),
        sa.Column('start_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('end_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['post_id'], ['posts.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_banners_status', 'banners', ['status'], unique=False)

    # 帖子置顶（管理员操作）
    op.add_column('posts', sa.Column('is_pinned', sa.Boolean(), nullable=True, server_default=sa.text('false')))
    op.add_column('posts', sa.Column('pinned_at', sa.DateTime(timezone=True), nullable=True))
    op.create_index('ix_posts_is_pinned', 'posts', ['is_pinned'], unique=False)
    # 存量数据补默认值后收紧约束
    op.execute('UPDATE posts SET is_pinned = false WHERE is_pinned IS NULL')
    op.alter_column('posts', 'is_pinned', nullable=False)

    # 举报处理留痕
    op.add_column('reports', sa.Column('handled_by', sa.UUID(), nullable=True))
    op.add_column('reports', sa.Column('handled_at', sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key('fk_reports_handled_by_users', 'reports', 'users', ['handled_by'], ['id'])


def downgrade() -> None:
    op.drop_constraint('fk_reports_handled_by_users', 'reports', type_='foreignkey')
    op.drop_column('reports', 'handled_at')
    op.drop_column('reports', 'handled_by')

    op.drop_index('ix_posts_is_pinned', table_name='posts')
    op.drop_column('posts', 'pinned_at')
    op.drop_column('posts', 'is_pinned')

    op.drop_index('ix_banners_status', table_name='banners')
    op.drop_table('banners')
