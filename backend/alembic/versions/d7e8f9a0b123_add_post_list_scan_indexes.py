"""add post list scan indexes and hot score leaderboard

帖子列表类查询的扫描面收敛（openspec/specs/optimization/spec.md「帖子列表类查询的
全表扫描」条目）：

- 搜索 `/api/v1/posts/search?q=…` 的 `content ILIKE '%q%'` 走 pg_trgm GIN 索引
  （仍是子串匹配，搜索语义不变）；配套 (is_featured, id) 复合索引支撑排序与
  键集分页，避免全表扫描后再 Sort。
- 推荐流 `/api/v1/posts`（不带 order，按热度分排序）改为榜单预计算：新增
  `post_hot_scores` 表与 `(score, post_id)` 索引，热度分由 worker 按固定周期算好
  落表，读接口只做索引扫描 + 键集分页。热度分公式本身不变。

pg_trgm 是 PostgreSQL 官方 contrib 扩展（trusted，非超级用户只要有建扩展权限即可
安装）。downgrade 只删本迁移创建的索引与表，**保留扩展本身**：扩展可能被运维或
其它对象共用，删扩展会让回滚变成破坏性操作。

Revision ID: d7e8f9a0b123
Revises: c1d2e3f4a5b6
Create Date: 2026-11-03
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd7e8f9a0b123'
down_revision: Union[str, None] = 'c1d2e3f4a5b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # pg_trgm：GIN 索引的 gin_trgm_ops 操作符类依赖它
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    # 搜索：content ILIKE '%q%' 的索引扫描（子串匹配语义不变）
    op.create_index(
        "ix_posts_content_trgm",
        "posts",
        ["content"],
        unique=False,
        postgresql_using="gin",
        postgresql_ops={"content": "gin_trgm_ops"},
    )
    # 搜索/精华流：排序 + 键集分页
    op.create_index("ix_posts_featured_id", "posts", ["is_featured", "id"], unique=False)
    # 推荐流榜单预计算
    op.create_table(
        'post_hot_scores',
        sa.Column('post_id', sa.BigInteger(), nullable=False),
        sa.Column('score', sa.Float(), nullable=False),
        sa.PrimaryKeyConstraint('post_id'),
    )
    op.create_index("ix_post_hot_scores_rank", "post_hot_scores", ["score", "post_id"], unique=False)
    op.create_table(
        'post_hot_score_state',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('computed_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('post_count', sa.Integer(), nullable=False, server_default='0'),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('post_hot_score_state')
    op.drop_index("ix_post_hot_scores_rank", table_name="post_hot_scores")
    op.drop_table('post_hot_scores')
    op.drop_index("ix_posts_featured_id", table_name="posts")
    op.drop_index("ix_posts_content_trgm", table_name="posts")
    # 刻意保留 pg_trgm 扩展：可能被运维或其它对象共用，删扩展会让回滚变成破坏性操作
