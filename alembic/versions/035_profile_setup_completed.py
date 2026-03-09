"""Add profile_setup_completed flag to therapists table

Revision ID: 035
Revises: 034
Create Date: 2026-03-09

Tracks whether the therapist has completed Step 2 (profile questionnaire).
Backfills TRUE for any therapist who already has onboarding_completed = TRUE
in their therapist_profiles row.
"""

from alembic import op
import sqlalchemy as sa

revision = "035"
down_revision = "034"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    conn.execute(sa.text(
        "ALTER TABLE therapists ADD COLUMN IF NOT EXISTS profile_setup_completed BOOLEAN DEFAULT FALSE;"
    ))
    # Backfill: any therapist whose profile is already marked complete
    conn.execute(sa.text("""
        UPDATE therapists
        SET profile_setup_completed = TRUE
        WHERE id IN (
            SELECT therapist_id FROM therapist_profiles
            WHERE onboarding_completed = TRUE
        )
        AND profile_setup_completed = FALSE;
    """))


def downgrade():
    try:
        conn = op.get_bind()
        conn.execute(sa.text("ALTER TABLE therapists DROP COLUMN IF EXISTS profile_setup_completed;"))
    except Exception:
        pass
