"""Phase 9 — UI Affordances: license fields + edit tracking

Revision ID: 022
Revises: 021
Create Date: 2026-03-06
"""

from alembic import op
import sqlalchemy as sa

revision = "022"
down_revision = "021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── therapist_profiles: dedicated license fields ───────────────────────────
    # These replace the certifications workaround used in Phase 5.
    # license_type: e.g. "פסיכולוג קליני מורשה", "עובד סוציאלי קליני"
    # license_number: e.g. "12345"
    op.add_column(
        "therapist_profiles",
        sa.Column("license_number", sa.String(64), nullable=True),
    )
    op.add_column(
        "therapist_profiles",
        sa.Column("license_type", sa.String(64), nullable=True),
    )

    # ── session_summaries: edit lifecycle tracking ────────────────────────────
    # edit_started_at: when the therapist first opened the editor for this summary
    # edit_ended_at: when the therapist approved (closed the edit cycle)
    # therapist_edit_count: number of edit-save calls before approval
    op.add_column(
        "session_summaries",
        sa.Column("edit_started_at", sa.DateTime, nullable=True),
    )
    op.add_column(
        "session_summaries",
        sa.Column("edit_ended_at", sa.DateTime, nullable=True),
    )
    op.add_column(
        "session_summaries",
        sa.Column("therapist_edit_count", sa.Integer, nullable=True, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("session_summaries", "therapist_edit_count")
    op.drop_column("session_summaries", "edit_ended_at")
    op.drop_column("session_summaries", "edit_started_at")
    op.drop_column("therapist_profiles", "license_type")
    op.drop_column("therapist_profiles", "license_number")
