"""Add accepted_terms_at timestamp to therapists

Revision ID: 037
Revises: 036
Create Date: 2026-03-11

Records when a therapist explicitly accepted the Terms & Privacy Policy.
NULL = account created before this requirement was introduced (backcompat).
"""

from alembic import op
import sqlalchemy as sa


revision = "037"
down_revision = "036"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        conn.execute(sa.text(
            "ALTER TABLE therapists ADD COLUMN IF NOT EXISTS accepted_terms_at TIMESTAMP DEFAULT NULL;"
        ))
    else:
        try:
            conn.execute(sa.text(
                "ALTER TABLE therapists ADD COLUMN accepted_terms_at TIMESTAMP DEFAULT NULL;"
            ))
        except Exception:
            pass  # Column already exists


def downgrade():
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        conn.execute(sa.text(
            "ALTER TABLE therapists DROP COLUMN IF EXISTS accepted_terms_at;"
        ))
