"""add user_follows table

Revision ID: f7a9c2d4e506
Revises: e6f8a1b3c405
Create Date: 2026-07-25
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f7a9c2d4e506'
down_revision: Union[str, None] = 'e6f8a1b3c405'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'user_follows',
        sa.Column('follower_id', sa.UUID(), nullable=False),
        sa.Column('followee_id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['follower_id'], ['users.id']),
        sa.ForeignKeyConstraint(['followee_id'], ['users.id']),
        sa.PrimaryKeyConstraint('follower_id', 'followee_id'),
    )
    op.create_index('ix_user_follows_followee', 'user_follows', ['followee_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_user_follows_followee', table_name='user_follows')
    op.drop_table('user_follows')
