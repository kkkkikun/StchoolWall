"""add admin roles

Revision ID: c8f3a6b2d901
Revises: d7e8f9a0b123
Create Date: 2026-11-09
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'c8f3a6b2d901'
down_revision: Union[str, None] = 'd7e8f9a0b123'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('admin_users', sa.Column('role', sa.String(20), nullable=False, server_default='admin'))
    op.create_check_constraint('ck_admin_users_role', 'admin_users', "role IN ('admin', 'owner')")
    op.execute("UPDATE admin_users SET role = 'owner' WHERE username = 'swadmin'")


def downgrade() -> None:
    op.drop_constraint('ck_admin_users_role', 'admin_users', type_='check')
    op.drop_column('admin_users', 'role')
