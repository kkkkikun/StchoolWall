"""add sensitive_words + moderation_records (自动审核：本地规则层 + 审核记录)

Revision ID: e8b1c4f7a2d9
Revises: 3fa1e19abdf2
Create Date: 2026-09-03 14:20:00.000000

种子词仅供 dev/prod 起步（测试库每测 TRUNCATE，测试自播数据）；
hard 命中直接拒绝，gray 命中转人工，管理端可增删改。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision: str = 'e8b1c4f7a2d9'
down_revision: Union[str, None] = '3fa1e19abdf2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SEED_WORDS = [
    ("代考", "hard"), ("代写包过", "hard"), ("枪手", "hard"), ("刷单返利", "hard"),
    ("兼职刷单", "hard"), ("高利贷", "hard"), ("赌博", "hard"), ("博彩", "hard"),
    ("毒品", "hard"), ("洗钱", "hard"),
    ("去死", "gray"), ("滚蛋", "gray"), ("脑子有病", "gray"), ("垃圾人", "gray"),
    ("一夜情", "gray"), ("约吗", "gray"), ("素质低下", "gray"), ("恶心人", "gray"),
    ("傻缺", "gray"), ("贱人", "gray"),
]


def upgrade() -> None:
    op.create_table(
        'sensitive_words',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('word', sa.String(50), nullable=False),
        sa.Column('level', sa.String(10), nullable=False),
        sa.Column('created_by', sa.String(36), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.UniqueConstraint('word', name='uq_sensitive_words_word'),
    )
    op.create_index('ix_sensitive_words_level', 'sensitive_words', ['level'])

    op.create_table(
        'moderation_records',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('post_id', sa.BigInteger(), sa.ForeignKey('posts.id'), nullable=False),
        sa.Column('source', sa.String(20), nullable=False),
        sa.Column('verdict', sa.String(10), nullable=False),
        sa.Column('matched', JSONB(), nullable=True),
        sa.Column('reason', sa.String(500), nullable=True),
        sa.Column('trace_id', sa.String(64), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
    )
    op.create_index('ix_moderation_records_post_id', 'moderation_records', ['post_id'])
    op.create_index('ix_moderation_records_source', 'moderation_records', ['source'])
    op.create_index('ix_moderation_records_verdict', 'moderation_records', ['verdict'])
    op.create_index('ix_moderation_records_created_at', 'moderation_records', ['created_at'])

    words = sa.table(
        'sensitive_words',
        sa.column('word', sa.String),
        sa.column('level', sa.String),
    )
    op.bulk_insert(words, [{"word": w, "level": lv} for w, lv in SEED_WORDS])


def downgrade() -> None:
    op.drop_index('ix_moderation_records_created_at', table_name='moderation_records')
    op.drop_index('ix_moderation_records_verdict', table_name='moderation_records')
    op.drop_index('ix_moderation_records_source', table_name='moderation_records')
    op.drop_index('ix_moderation_records_post_id', table_name='moderation_records')
    op.drop_table('moderation_records')
    op.drop_index('ix_sensitive_words_level', table_name='sensitive_words')
    op.drop_table('sensitive_words')
