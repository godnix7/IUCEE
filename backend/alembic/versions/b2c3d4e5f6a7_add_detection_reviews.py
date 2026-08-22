"""add detection_reviews table (human QA / relabel with provenance)

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-08-18
"""
from alembic import op
import sqlalchemy as sa


revision = "b2c3d4e5f6a7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "detection_reviews",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("analysis_id", sa.Integer(), sa.ForeignKey("imagery_analyses.id"), nullable=False),
        sa.Column("feature_id", sa.Integer(), sa.ForeignKey("spatial_features.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reviewer_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("original_label", sa.String(), nullable=False),
        sa.Column("original_source", sa.String(), nullable=True),
        sa.Column("corrected_label", sa.String(), nullable=True),
        sa.Column("review_source", sa.String(), nullable=True, server_default="human_review"),
        sa.Column("status", sa.String(), nullable=True, server_default="pending"),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_detection_reviews_analysis_id", "detection_reviews", ["analysis_id"])
    op.create_index("ix_detection_reviews_feature_id", "detection_reviews", ["feature_id"], unique=True)
    op.create_index("ix_detection_reviews_status", "detection_reviews", ["status"])


def downgrade() -> None:
    op.drop_index("ix_detection_reviews_status", table_name="detection_reviews")
    op.drop_index("ix_detection_reviews_feature_id", table_name="detection_reviews")
    op.drop_index("ix_detection_reviews_analysis_id", table_name="detection_reviews")
    op.drop_table("detection_reviews")
