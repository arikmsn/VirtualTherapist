"""Add intended_plan column to therapists

Revision ID: 036
Revises: 035
Create Date: 2026-03-10

Stores the marketing plan the user clicked before registering (e.g. 'pro').
NULL means the user registered without a plan query param — no behaviour change.
"""

from alembic import op
import sqlalchemy as sa


revision = "036"
down_revision = "035"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        conn.execute(sa.text(
            "ALTER TABLE therapists ADD COLUMN IF NOT EXISTS intended_plan VARCHAR(50) DEFAULT NULL;"
        ))
    else:
        # SQLite: ALTER TABLE ADD COLUMN is supported
        try:
            conn.execute(sa.text(
                "ALTER TABLE therapists ADD COLUMN intended_plan VARCHAR(50) DEFAULT NULL;"
            ))
        except Exception:
            pass  # Column already exists


def downgrade():
    # SQLite does not support DROP COLUMN in older versions; skip for dev
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        conn.execute(sa.text(
            "ALTER TABLE therapists DROP COLUMN IF EXISTS intended_plan;"
        ))
