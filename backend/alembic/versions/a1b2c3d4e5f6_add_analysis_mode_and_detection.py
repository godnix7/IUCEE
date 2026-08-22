"""add analysis_mode and detection outputs to imagery_analyses

Revision ID: a1b2c3d4e5f6
Revises: f1d2c3b4a5e6
Create Date: 2026-08-18

Adds dual-mode analysis support:
  - analysis_mode: 'segmentation' (LoveDA land-cover) | 'detection' (COCO object detection)
  - detection_overlay_key: MinIO key of the annotated detection image
  - detection_summary: JSON per-class detection counts + totals
"""
from alembic import op
import sqlalchemy as sa


revision = "a1b2c3d4e5f6"
down_revision = "f1d2c3b4a5e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "imagery_analyses",
        sa.Column("analysis_mode", sa.String(), nullable=True, server_default="segmentation"),
    )
    op.add_column("imagery_analyses", sa.Column("detection_overlay_key", sa.String(), nullable=True))
    op.add_column("imagery_analyses", sa.Column("detection_summary", sa.JSON(), nullable=True))
    op.create_index(
        "ix_imagery_analyses_analysis_mode", "imagery_analyses", ["analysis_mode"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_imagery_analyses_analysis_mode", table_name="imagery_analyses")
    op.drop_column("imagery_analyses", "detection_summary")
    op.drop_column("imagery_analyses", "detection_overlay_key")
    op.drop_column("imagery_analyses", "analysis_mode")
