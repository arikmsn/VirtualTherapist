"""Add usage_type column to ai_generation_log

Revision ID: 031
Revises: 030
Create Date: 2026-03-09

Adds:
- ai_generation_log.usage_type — TEXT, nullable, derived at write time
  Values: 'text_claude', 'text_openai', 'transcription'
"""

from alembic import op
import sqlalchemy as sa

revision = "031"
down_revision = "030"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    conn.execute(sa.text(
        "ALTER TABLE ai_generation_log ADD COLUMN IF NOT EXISTS usage_type TEXT DEFAULT 'text_claude';"
    ))


def downgrade():
    # PostgreSQL doesn't support DROP COLUMN IF EXISTS in older versions; best-effort
    try:
        conn = op.get_bind()
        conn.execute(sa.text("ALTER TABLE ai_generation_log DROP COLUMN IF EXISTS usage_type;"))
    except Exception:
        pass
