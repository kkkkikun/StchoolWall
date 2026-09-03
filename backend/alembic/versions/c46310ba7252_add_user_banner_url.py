"""add user banner_url

Revision ID: c46310ba7252
Revises: 360667a805e8
Create Date: 2026-09-03 09:23:19.628173

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c46310ba7252'
down_revision: Union[str, None] = '360667a805e8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('banner_url', sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'banner_url')
