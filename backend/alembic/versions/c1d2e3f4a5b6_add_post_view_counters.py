"""add post_view_counters table

浏览计数的异步聚合缓冲：详情页浏览数只写本表，由 worker 周期性折叠回
posts.view_count，避免热点帖详情浏览与点赞/评论争同一行锁。

刻意不加到 posts.id 的外键：外键检查会对 posts 行取 KEY SHARE 锁，与热点帖的
行锁冲突，会把拆掉的串行点重新引回来；本表只是计数缓冲，孤儿行无害。

Revision ID: c1d2e3f4a5b6
Revises: d4e6f8a1b357
Create Date: 2026-11-03
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c1d2e3f4a5b6'
down_revision: Union[str, None] = 'd4e6f8a1b357'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'post_view_counters',
        sa.Column('post_id', sa.BigInteger(), nullable=False),
        sa.Column('views', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('post_id'),
    )


def downgrade() -> None:
    op.drop_table('post_view_counters')
