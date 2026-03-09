"""Confirm years_of_experience column is VARCHAR (safe no-op)

Revision ID: 034
Revises: 033
Create Date: 2026-03-09

years_of_experience was created as String(50)/VARCHAR in migration 006.
This migration makes the intent explicit for Supabase PostgreSQL and
allows free-text values like "3-5 שנים" or "10+".
"""

from alembic import op
import sqlalchemy as sa

revision = "034"
down_revision = "033"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    dialect = conn.dialect.name
    if dialect == "postgresql":
        # Widen to VARCHAR(100) — safe even if already VARCHAR(50)
        conn.execute(sa.text(
            "ALTER TABLE therapist_profiles "
            "ALTER COLUMN years_of_experience TYPE VARCHAR(100);"
        ))
    # SQLite: already TEXT, no ALTER COLUMN TYPE needed


def downgrade():
    pass  # no-op — narrowing VARCHAR is risky and not needed
