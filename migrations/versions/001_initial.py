"""Full V1 schema.

Revision ID: 001_initial
Revises:
Create Date: V1 initial

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ads",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("brief_id", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=True),
        sa.Column("primary_text", sa.Text(), nullable=True),
        sa.Column("headline", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("cta_button", sa.Text(), nullable=True),
        sa.Column("image_url", sa.Text(), nullable=True),
        sa.Column("image_prompt", sa.Text(), nullable=True),
        sa.Column("final_score", sa.Float(), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.Text(), nullable=True),
    )
    op.create_table(
        "briefs",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("audience", sa.Text(), nullable=True),
        sa.Column("campaign_goal", sa.Text(), nullable=True),
        sa.Column("product", sa.Text(), nullable=True),
        sa.Column("hook_style", sa.Text(), nullable=True),
        sa.Column("platform", sa.Text(), nullable=True),
        sa.Column("offer", sa.Text(), nullable=True),
        sa.Column("urgency", sa.Text(), nullable=True),
        sa.Column("social_proof", sa.Text(), nullable=True),
        sa.Column("inferred_profile_id", sa.Text(), nullable=True),
        sa.Column("inferred_length_target", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=True),
    )
    op.create_table(
        "evaluations",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("ad_id", sa.Text(), nullable=True),
        sa.Column("attempt_number", sa.Integer(), nullable=True),
        sa.Column("weighted_score", sa.Float(), nullable=True),
        sa.Column("knockout_passed", sa.Boolean(), nullable=True),
        sa.Column("knockout_failures", sa.Text(), nullable=True),
        sa.Column("requires_human_review", sa.Boolean(), nullable=True),
        sa.Column("flags", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("confidence_level", sa.Text(), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=True),
    )
    op.create_table(
        "dimension_scores",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("evaluation_id", sa.Text(), nullable=True),
        sa.Column("dimension", sa.Text(), nullable=True),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("self_confidence", sa.Float(), nullable=True),
    )
    op.create_table(
        "iterations",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("ad_id", sa.Text(), nullable=True),
        sa.Column("attempt_number", sa.Integer(), nullable=True),
        sa.Column("tier", sa.Text(), nullable=True),
        sa.Column("target_dimension", sa.Text(), nullable=True),
        sa.Column("strategy", sa.Text(), nullable=True),
        sa.Column("score_before", sa.Float(), nullable=True),
        sa.Column("score_after", sa.Float(), nullable=True),
        sa.Column("dimensions_improved", sa.Text(), nullable=True),
        sa.Column("dimensions_regressed", sa.Text(), nullable=True),
        sa.Column("oscillation_detected", sa.Boolean(), nullable=True),
        sa.Column("cost_usd", sa.Float(), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=True),
    )
    op.create_table(
        "token_usage",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("ad_id", sa.Text(), nullable=True),
        sa.Column("brief_id", sa.Text(), nullable=True),
        sa.Column("operation", sa.Text(), nullable=True),
        sa.Column("provider", sa.Text(), nullable=True),
        sa.Column("model", sa.Text(), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("cost_usd", sa.Float(), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=True),
    )
    op.create_table(
        "reference_ads",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("ad_library_id", sa.Text(), nullable=True),
        sa.Column("competitor", sa.Text(), nullable=True),
        sa.Column("primary_text", sa.Text(), nullable=True),
        sa.Column("headline", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("cta_button", sa.Text(), nullable=True),
        sa.Column("platform", sa.Text(), nullable=True),
        sa.Column("ad_format", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("carousel_id", sa.Text(), nullable=True),
        sa.Column("raw_html", sa.Text(), nullable=True),
        sa.Column("calibration_quality", sa.Text(), nullable=True),
        sa.Column("calibration_score", sa.Float(), nullable=True),
        sa.Column("scraped_at", sa.Text(), nullable=True),
    )
    op.create_index("ix_reference_ads_ad_library_id", "reference_ads", ["ad_library_id"], unique=True)
    op.create_table(
        "batch_checkpoints",
        sa.Column("run_id", sa.Text(), nullable=False),
        sa.Column("brief_id", sa.Text(), nullable=False),
        sa.Column("completed_at", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("run_id", "brief_id"),
    )
    op.create_table(
        "ratchet_history",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("previous_threshold", sa.Float(), nullable=True),
        sa.Column("new_threshold", sa.Float(), nullable=True),
        sa.Column("trigger_avg_score", sa.Float(), nullable=True),
        sa.Column("window_size", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("ratchet_history")
    op.drop_table("batch_checkpoints")
    op.drop_index("ix_reference_ads_ad_library_id", table_name="reference_ads")
    op.drop_table("reference_ads")
    op.drop_table("token_usage")
    op.drop_table("iterations")
    op.drop_table("dimension_scores")
    op.drop_table("evaluations")
    op.drop_table("briefs")
    op.drop_table("ads")
