"""Add intro_wizard_completed column to therapists

Revision ID: 033
Revises: 032
Create Date: 2026-03-09

Adds:
- therapists.intro_wizard_completed — BOOLEAN DEFAULT FALSE
  Set to TRUE when therapist completes or skips the first-time data wizard.
  Never show the wizard again after that.
"""

from alembic import op
import sqlalchemy as sa

revision = "033"
down_revision = "032"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    conn.execute(sa.text(
        "ALTER TABLE therapists ADD COLUMN IF NOT EXISTS intro_wizard_completed BOOLEAN DEFAULT FALSE;"
    ))


def downgrade():
    try:
        conn = op.get_bind()
        conn.execute(sa.text("ALTER TABLE therapists DROP COLUMN IF EXISTS intro_wizard_completed;"))
    except Exception:
        pass
