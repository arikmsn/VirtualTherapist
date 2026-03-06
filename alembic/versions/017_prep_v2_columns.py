"""Pre-Session Prep 2.0 — add prep columns to sessions table.

Revision ID: 017
Revises: 016
Create Date: 2026-03-06
"""

import sqlalchemy as sa
from alembic import op

revision = "017"
down_revision = "016"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("sessions", sa.Column("prep_json", sa.JSON(), nullable=True))
    op.add_column("sessions", sa.Column("prep_mode", sa.String(32), nullable=True))
    op.add_column("sessions", sa.Column("prep_completeness_score", sa.Float(), nullable=True))
    op.add_column("sessions", sa.Column("prep_completeness_data", sa.JSON(), nullable=True))
    op.add_column("sessions", sa.Column("prep_generated_at", sa.DateTime(), nullable=True))


def downgrade():
    op.drop_column("sessions", "prep_generated_at")
    op.drop_column("sessions", "prep_completeness_data")
    op.drop_column("sessions", "prep_completeness_score")
    op.drop_column("sessions", "prep_mode")
    op.drop_column("sessions", "prep_json")
