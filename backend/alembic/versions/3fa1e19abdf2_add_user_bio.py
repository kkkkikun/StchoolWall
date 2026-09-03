"""add user bio

Revision ID: 3fa1e19abdf2
Revises: c46310ba7252
Create Date: 2026-09-03 10:52:49.638731

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3fa1e19abdf2'
down_revision: Union[str, None] = 'c46310ba7252'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('bio', sa.String(length=200), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'bio')
