"""Add fingerprint caching columns and treatment plan metadata

Revision ID: 025
Revises: 024
Create Date: 2026-03-06

Adds:
- treatment_plans.source (VARCHAR) — origin of plan: "ai_generated" | "manual"
- treatment_plans.title (VARCHAR) — optional human-readable version label
- sessions.prep_input_fingerprint (TEXT) — SHA-256 of inputs used for prep generation
- sessions.prep_input_fingerprint_version (INTEGER) — schema version for the fingerprint
- session_summaries.ai_input_fingerprint (TEXT) — SHA-256 of inputs used for summary generation
- session_summaries.ai_input_fingerprint_version (INTEGER) — schema version
"""

from alembic import op
import sqlalchemy as sa

revision = "025"
down_revision = "024"
branch_labels = None
depends_on = None


def upgrade():
    # treatment_plans: source + title for version history display
    op.add_column(
        "treatment_plans",
        sa.Column("source", sa.String(64), nullable=True),
    )
    op.add_column(
        "treatment_plans",
        sa.Column("title", sa.String(255), nullable=True),
    )

    # sessions: prep fingerprint for 10-minute cache invalidation
    op.add_column(
        "sessions",
        sa.Column("prep_input_fingerprint", sa.Text, nullable=True),
    )
    op.add_column(
        "sessions",
        sa.Column("prep_input_fingerprint_version", sa.Integer, nullable=True),
    )

    # session_summaries: summary generation fingerprint
    op.add_column(
        "session_summaries",
        sa.Column("ai_input_fingerprint", sa.Text, nullable=True),
    )
    op.add_column(
        "session_summaries",
        sa.Column("ai_input_fingerprint_version", sa.Integer, nullable=True),
    )


def downgrade():
    op.drop_column("treatment_plans", "source")
    op.drop_column("treatment_plans", "title")
    op.drop_column("sessions", "prep_input_fingerprint")
    op.drop_column("sessions", "prep_input_fingerprint_version")
    op.drop_column("session_summaries", "ai_input_fingerprint")
    op.drop_column("session_summaries", "ai_input_fingerprint_version")
