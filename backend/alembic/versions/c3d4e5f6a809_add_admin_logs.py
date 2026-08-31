"""add admin_logs table

Revision ID: c3d4e5f6a809
Revises: b2c3d4e5f708
Create Date: 2026-08-31
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision: str = 'c3d4e5f6a809'
down_revision: Union[str, None] = 'b2c3d4e5f708'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'admin_logs',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('admin_id', sa.String(36), nullable=False),
        sa.Column('admin_name', sa.String(100), nullable=False),
        sa.Column('source', sa.String(10), nullable=False),
        sa.Column('action', sa.String(50), nullable=False),
        sa.Column('target_type', sa.String(20), nullable=True),
        sa.Column('target_id', sa.String(50), nullable=True),
        sa.Column('detail', JSONB(), nullable=True),
        sa.Column('ip', sa.String(45), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_admin_logs_admin_id', 'admin_logs', ['admin_id'], unique=False)
    op.create_index('ix_admin_logs_action', 'admin_logs', ['action'], unique=False)
    op.create_index('ix_admin_logs_created_at', 'admin_logs', ['created_at'], unique=False)
    op.create_index('ix_admin_logs_admin_time', 'admin_logs', ['admin_id', sa.text('created_at DESC')], unique=False)


def downgrade() -> None:
    op.drop_index('ix_admin_logs_admin_time', table_name='admin_logs')
    op.drop_index('ix_admin_logs_created_at', table_name='admin_logs')
    op.drop_index('ix_admin_logs_action', table_name='admin_logs')
    op.drop_index('ix_admin_logs_admin_id', table_name='admin_logs')
    op.drop_table('admin_logs')
