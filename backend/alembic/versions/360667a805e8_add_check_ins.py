"""add check_ins

Revision ID: 360667a805e8
Revises: 8dd9dd74cb0a
Create Date: 2026-09-02 10:47:35.639462

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '360667a805e8'
down_revision: Union[str, None] = '8dd9dd74cb0a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'check_ins',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.UUID(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('check_date', sa.Date(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.UniqueConstraint('user_id', 'check_date', name='uq_checkin_user_date'),
    )
    op.create_index('ix_check_ins_user_id', 'check_ins', ['user_id'])


def downgrade() -> None:
    op.drop_index('ix_check_ins_user_id', table_name='check_ins')
    op.drop_table('check_ins')
