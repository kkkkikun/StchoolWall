"""add party tables (parties + party_members)

Revision ID: d5c7e9f1a203
Revises: c2b4f6a8d910
Create Date: 2026-07-08
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd5c7e9f1a203'
down_revision: Union[str, None] = 'c2b4f6a8d910'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'parties',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('type', sa.String(length=10), nullable=False),
        sa.Column('category', sa.String(length=20), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('total', sa.Integer(), nullable=False),
        sa.Column('joined_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('status', sa.SmallInteger(), nullable=False, server_default='1'),
        sa.Column('meet_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('location', sa.String(length=100), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_parties_user_id'), 'parties', ['user_id'], unique=False)
    op.create_index(op.f('ix_parties_category'), 'parties', ['category'], unique=False)
    op.create_index(op.f('ix_parties_created_at'), 'parties', ['created_at'], unique=False)

    op.create_table(
        'party_members',
        sa.Column('party_id', sa.BigInteger(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('joined_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['party_id'], ['parties.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('party_id', 'user_id'),
    )


def downgrade() -> None:
    op.drop_table('party_members')
    op.drop_index(op.f('ix_parties_created_at'), table_name='parties')
    op.drop_index(op.f('ix_parties_category'), table_name='parties')
    op.drop_index(op.f('ix_parties_user_id'), table_name='parties')
    op.drop_table('parties')
