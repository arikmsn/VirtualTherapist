"""Add transcript column to session_summaries

Revision ID: 003_add_transcript_to_summaries
Revises: 002_add_session_time_and_summary_status
Create Date: 2026-02-18
"""
from alembic import op
import sqlalchemy as sa

revision = "003_add_transcript_to_summaries"
down_revision = "002_add_session_time_and_summary_status"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("session_summaries", sa.Column("transcript", sa.Text, nullable=True))


def downgrade() -> None:
    op.drop_column("session_summaries", "transcript")
