"""add activities table and banner.activity_id

Revision ID: a7b8c9d0e1f2
Revises: b4d7e2f9a1c5
Create Date: 2026-09-22
"""
from alembic import op
import sqlalchemy as sa


revision = 'a7b8c9d0e1f2'
down_revision = 'b4d7e2f9a1c5'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'activities',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('title', sa.String(length=100), nullable=False),
        sa.Column('image_url', sa.String(length=500), nullable=True),
        sa.Column('summary', sa.String(length=200), nullable=True),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('location', sa.String(length=100), nullable=True),
        sa.Column('start_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('end_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', sa.SmallInteger(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_activities_status', 'activities', ['status'], unique=False)
    op.add_column('banners', sa.Column('activity_id', sa.BigInteger(), nullable=True))


def downgrade() -> None:
    op.drop_column('banners', 'activity_id')
    op.drop_index('ix_activities_status', table_name='activities')
    op.drop_table('activities')
