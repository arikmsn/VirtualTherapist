"""Add must_change_password column to therapists

Revision ID: 032
Revises: 031
Create Date: 2026-03-09

Adds:
- therapists.must_change_password — BOOLEAN DEFAULT FALSE
  Set to TRUE when admin sends a temporary password.
  Reset to FALSE when therapist successfully changes their password.
"""

from alembic import op
import sqlalchemy as sa

revision = "032"
down_revision = "031"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    conn.execute(sa.text(
        "ALTER TABLE therapists ADD COLUMN IF NOT EXISTS must_change_password BOOLEAN DEFAULT FALSE;"
    ))


def downgrade():
    try:
        conn = op.get_bind()
        conn.execute(sa.text("ALTER TABLE therapists DROP COLUMN IF EXISTS must_change_password;"))
    except Exception:
        pass
