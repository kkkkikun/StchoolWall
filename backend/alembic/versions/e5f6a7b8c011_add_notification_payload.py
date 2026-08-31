"""add notification payload/batch_id (announcements)

Revision ID: e5f6a7b8c011
Revises: d4e5f6a7b910
Create Date: 2026-08-31
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision: str = 'e5f6a7b8c011'
down_revision: Union[str, None] = 'd4e5f6a7b910'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('notifications', sa.Column('payload', JSONB(), nullable=True))
    op.add_column('notifications', sa.Column('batch_id', sa.String(36), nullable=True))
    op.create_index('ix_notifications_batch_id', 'notifications', ['batch_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_notifications_batch_id', table_name='notifications')
    op.drop_column('notifications', 'batch_id')
    op.drop_column('notifications', 'payload')
