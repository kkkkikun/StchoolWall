"""add admin_users table

Revision ID: b2c3d4e5f708
Revises: a1b2c3d4e607
Create Date: 2026-08-31
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision: str = 'b2c3d4e5f708'
down_revision: Union[str, None] = 'a1b2c3d4e607'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'admin_users',
        sa.Column('id', UUID(), nullable=False),
        sa.Column('username', sa.String(50), nullable=False),
        sa.Column('password_hash', sa.String(100), nullable=False),
        sa.Column('nickname', sa.String(50), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('pwd_version', sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('username'),
    )
    op.create_index('ix_admin_users_username', 'admin_users', ['username'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_admin_users_username', table_name='admin_users')
    op.drop_table('admin_users')
