"""add post is_featured

Revision ID: 8dd9dd74cb0a
Revises: e5f6a7b8c011
Create Date: 2026-09-01 21:38:45.039412

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8dd9dd74cb0a'
down_revision: Union[str, None] = 'e5f6a7b8c011'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('posts', sa.Column('is_featured', sa.Boolean(), nullable=False, server_default=sa.text('false')))
    op.add_column('posts', sa.Column('featured_at', sa.DateTime(timezone=True), nullable=True))
    op.create_index('ix_posts_is_featured', 'posts', ['is_featured'])


def downgrade() -> None:
    op.drop_index('ix_posts_is_featured', table_name='posts')
    op.drop_column('posts', 'featured_at')
    op.drop_column('posts', 'is_featured')
