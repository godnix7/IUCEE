"""add analysis_reviews table (image-level human verdict + re-send)

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-08-19
"""
from alembic import op
import sqlalchemy as sa


revision = "c3d4e5f6a7b8"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "analysis_reviews",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("analysis_id", sa.Integer(), sa.ForeignKey("imagery_analyses.id"), nullable=False),
        sa.Column("reviewer_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("status", sa.String(), nullable=True, server_default="pending"),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("review_source", sa.String(), nullable=True, server_default="human_review"),
        sa.Column("resent", sa.Boolean(), nullable=True, server_default=sa.false()),
        sa.Column("resent_job_id", sa.Integer(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_analysis_reviews_analysis_id", "analysis_reviews", ["analysis_id"], unique=True)
    op.create_index("ix_analysis_reviews_status", "analysis_reviews", ["status"])


def downgrade() -> None:
    op.drop_index("ix_analysis_reviews_status", table_name="analysis_reviews")
    op.drop_index("ix_analysis_reviews_analysis_id", table_name="analysis_reviews")
    op.drop_table("analysis_reviews")
