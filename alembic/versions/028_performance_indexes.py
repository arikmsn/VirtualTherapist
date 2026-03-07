"""Performance indexes and AI caching columns

Revision ID: 028
Revises: 027
Create Date: 2026-03-08

Adds:
- Composite index sessions(therapist_id, session_date) — covers Dashboard by-date query
- Index session_summaries(approved_by_therapist) — covers every AI pipeline filter
- Index audio_clips(session_id) — SQLite does not auto-index FK columns
- Index exercises(session_summary_id) — used in tasks-tab origin lookup
- input_fingerprint + input_fingerprint_version on deep_summaries — skip-regen caching
- input_fingerprint + input_fingerprint_version on treatment_plans  — skip-regen caching
"""

from alembic import op
import sqlalchemy as sa

revision = "028"
down_revision = "027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Composite index: sessions(therapist_id, session_date)
    with op.batch_alter_table("sessions") as batch_op:
        batch_op.create_index(
            "ix_sessions_therapist_date",
            ["therapist_id", "session_date"],
        )

    # Index: session_summaries(approved_by_therapist)
    with op.batch_alter_table("session_summaries") as batch_op:
        batch_op.create_index(
            "ix_session_summaries_approved",
            ["approved_by_therapist"],
        )

    # Index: audio_clips(session_id)
    with op.batch_alter_table("audio_clips") as batch_op:
        batch_op.create_index(
            "ix_audio_clips_session_id",
            ["session_id"],
        )

    # Index: exercises(session_summary_id)
    with op.batch_alter_table("exercises") as batch_op:
        batch_op.create_index(
            "ix_exercises_session_summary_id",
            ["session_summary_id"],
        )

    # Fingerprint columns: deep_summaries
    with op.batch_alter_table("deep_summaries") as batch_op:
        batch_op.add_column(sa.Column("input_fingerprint", sa.Text, nullable=True))
        batch_op.add_column(sa.Column("input_fingerprint_version", sa.Integer, nullable=True))

    # Fingerprint columns: treatment_plans
    with op.batch_alter_table("treatment_plans") as batch_op:
        batch_op.add_column(sa.Column("input_fingerprint", sa.Text, nullable=True))
        batch_op.add_column(sa.Column("input_fingerprint_version", sa.Integer, nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("treatment_plans") as batch_op:
        batch_op.drop_column("input_fingerprint_version")
        batch_op.drop_column("input_fingerprint")

    with op.batch_alter_table("deep_summaries") as batch_op:
        batch_op.drop_column("input_fingerprint_version")
        batch_op.drop_column("input_fingerprint")

    with op.batch_alter_table("exercises") as batch_op:
        batch_op.drop_index("ix_exercises_session_summary_id")

    with op.batch_alter_table("audio_clips") as batch_op:
        batch_op.drop_index("ix_audio_clips_session_id")

    with op.batch_alter_table("session_summaries") as batch_op:
        batch_op.drop_index("ix_session_summaries_approved")

    with op.batch_alter_table("sessions") as batch_op:
        batch_op.drop_index("ix_sessions_therapist_date")
