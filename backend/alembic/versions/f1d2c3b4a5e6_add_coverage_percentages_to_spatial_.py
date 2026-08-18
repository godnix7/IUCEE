"""Add coverage percentages to spatial analytics

Revision ID: f1d2c3b4a5e6
Revises: 88be84c99bf8
Create Date: 2026-08-18 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f1d2c3b4a5e6'
down_revision = '88be84c99bf8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('spatial_analytics', sa.Column('barren_cover_pct', sa.Float(), nullable=True))
    op.add_column('spatial_analytics', sa.Column('agriculture_cover_pct', sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column('spatial_analytics', 'agriculture_cover_pct')
    op.drop_column('spatial_analytics', 'barren_cover_pct')