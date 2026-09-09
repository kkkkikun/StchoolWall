"""add users.web_password_hash (网页版登录)

Revision ID: f2a8d5c1e3b7
Revises: e8b1c4f7a2d9
Create Date: 2026-09-04 15:30:00.000000

网页测试版部署的账号密码（bcrypt）；小程序用户该列为空。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f2a8d5c1e3b7'
down_revision: Union[str, None] = 'e8b1c4f7a2d9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('web_password_hash', sa.String(100), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'web_password_hash')
