"""drop reports.handled_by FK (console admin ids live in admin_users)

Revision ID: d4e5f6a7b910
Revises: c3d4e5f6a809
Create Date: 2026-08-31
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'd4e5f6a7b910'
down_revision: Union[str, None] = 'c3d4e5f6a809'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # handled_by 现在可能是 console 体系 admin（不在 users 表），外键不再成立
    op.drop_constraint('fk_reports_handled_by_users', 'reports', type_='foreignkey')


def downgrade() -> None:
    # 回滚前需确保 handled_by 无 users 表之外的值。
    # handled_by 的类型会随链上的 529bf8becb3f 在 UUID 与 varchar(36) 之间来回切换，
    # 比较时统一转文本，否则整链回退到这条迁移时会报「operator does not exist: uuid = text」。
    op.execute("DELETE FROM reports WHERE handled_by IS NOT NULL AND handled_by::text NOT IN (SELECT id::text FROM users)")
    op.create_foreign_key('fk_reports_handled_by_users', 'reports', 'users', ['handled_by'], ['id'])
