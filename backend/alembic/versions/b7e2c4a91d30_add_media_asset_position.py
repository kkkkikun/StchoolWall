"""media_asset_position

Revision ID: b7e2c4a91d30
Revises: 529bf8becb3f
Create Date: 2026-10-30

给 media_assets 增加 position 列：记录图片被绑定到内容时的展示顺序，
即用户在小程序发布页里选择的先后顺序。绑定前为 NULL。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b7e2c4a91d30'
down_revision: Union[str, None] = '529bf8becb3f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('media_assets', sa.Column('position', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('media_assets', 'position')
