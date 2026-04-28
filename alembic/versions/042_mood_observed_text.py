"""Widen session_summaries.mood_observed from VARCHAR(100) to TEXT

Fixes StringDataRightTruncation when AI generates a mood observation
longer than 100 characters.

Revision ID: 042
Revises: 041
Create Date: 2026-04-28
"""
from alembic import op
import sqlalchemy as sa

revision = "042"
down_revision = "041"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "session_summaries",
        "mood_observed",
        type_=sa.Text(),
        existing_nullable=True,
    )


def downgrade():
    op.alter_column(
        "session_summaries",
        "mood_observed",
        type_=sa.String(100),
        existing_nullable=True,
    )
