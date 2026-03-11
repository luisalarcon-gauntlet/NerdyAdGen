"""Add quality_failure table.

Revision ID: 002_quality_failure
Revises: 001_initial
Create Date: quality failure records

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "002_quality_failure"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "quality_failure",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("ad_id", sa.Text(), nullable=True),
        sa.Column("brief_id", sa.Text(), nullable=True),
        sa.Column("attempt_number", sa.Integer(), nullable=True),
        sa.Column("failure_pattern", sa.Text(), nullable=True),
        sa.Column("diagnosis_summary", sa.Text(), nullable=True),
        sa.Column("diagnosis_suggested_action", sa.Text(), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("quality_failure")
