"""add post.category column

Revision ID: e6f8a1b3c405
Revises: d5c7e9f1a203
Create Date: 2026-07-25
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e6f8a1b3c405'
down_revision: Union[str, None] = 'd5c7e9f1a203'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('posts', sa.Column('category', sa.String(length=20), nullable=True))
    op.create_index(op.f('ix_posts_category'), 'posts', ['category'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_posts_category'), table_name='posts')
    op.drop_column('posts', 'category')
