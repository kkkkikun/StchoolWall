"""add feedbacks table

Revision ID: d4e6f8a1b357
Revises: b7e2c4a91d30
Create Date: 2026-11-02
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'd4e6f8a1b357'
down_revision: Union[str, None] = 'b7e2c4a91d30'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'feedbacks',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=True),
        sa.Column('reporter_name', sa.String(length=64), nullable=True),
        sa.Column('category', sa.String(length=20), nullable=False),
        sa.Column('severity', sa.String(length=10), nullable=False, server_default='medium'),
        sa.Column('title', sa.String(length=120), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('page_url', sa.String(length=500), nullable=True),
        sa.Column('route', sa.String(length=120), nullable=True),
        sa.Column('user_agent', sa.String(length=300), nullable=True),
        sa.Column('viewport', sa.String(length=60), nullable=True),
        sa.Column('theme', sa.String(length=10), nullable=True),
        sa.Column('app_version', sa.String(length=64), nullable=True),
        sa.Column('client_ip', sa.String(length=45), nullable=True),
        sa.Column('diagnostics', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('screenshots', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('upload_token', sa.String(length=64), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='open'),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('handled_by', sa.String(length=36), nullable=True),
        sa.Column('handled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_feedbacks_user_id'), 'feedbacks', ['user_id'], unique=False)
    op.create_index(op.f('ix_feedbacks_category'), 'feedbacks', ['category'], unique=False)
    op.create_index(op.f('ix_feedbacks_status'), 'feedbacks', ['status'], unique=False)
    op.create_index(op.f('ix_feedbacks_created_at'), 'feedbacks', ['created_at'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_feedbacks_created_at'), table_name='feedbacks')
    op.drop_index(op.f('ix_feedbacks_status'), table_name='feedbacks')
    op.drop_index(op.f('ix_feedbacks_category'), table_name='feedbacks')
    op.drop_index(op.f('ix_feedbacks_user_id'), table_name='feedbacks')
    op.drop_table('feedbacks')
