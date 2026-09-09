"""add moderation_records.comment_id (评论审核记录)

Revision ID: b4d7e2f9a1c5
Revises: f2a8d5c1e3b7
Create Date: 2026-09-05 10:20:00.000000

评论接入本地审核：记录行 comment_id 指向被审评论（硬词拒绝时评论未创建，
comment_id 为空、post_id 指向被评帖）。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b4d7e2f9a1c5'
down_revision: Union[str, None] = 'f2a8d5c1e3b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('moderation_records',
                  sa.Column('comment_id', sa.BigInteger(), sa.ForeignKey('comments.id'), nullable=True))
    op.create_index('ix_moderation_records_comment_id', 'moderation_records', ['comment_id'])


def downgrade() -> None:
    op.drop_index('ix_moderation_records_comment_id', table_name='moderation_records')
    op.drop_column('moderation_records', 'comment_id')
