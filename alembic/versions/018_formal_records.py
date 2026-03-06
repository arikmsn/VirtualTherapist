"""Israeli Formal Record Support — new formal_records table + record_notes on session_summaries.

Revision ID: 018
Revises: 017
Create Date: 2026-03-06
"""

import sqlalchemy as sa
from alembic import op

revision = "018"
down_revision = "017"
branch_labels = None
depends_on = None


def upgrade():
    # 1. New formal_records table
    op.create_table(
        "formal_records",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("sessions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("patient_id", sa.Integer(), sa.ForeignKey("patients.id", ondelete="CASCADE"), nullable=False),
        sa.Column("therapist_id", sa.Integer(), sa.ForeignKey("therapists.id", ondelete="CASCADE"), nullable=False),
        sa.Column("record_type", sa.String(64), nullable=False),
        sa.Column("record_json", sa.JSON(), nullable=True),
        sa.Column("rendered_text", sa.Text(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="draft"),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.Column("model_used", sa.String(128), nullable=True),
        sa.Column("tokens_used", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    # 2. record_notes on session_summaries (deferred from Phase 1)
    op.add_column(
        "session_summaries",
        sa.Column("record_notes", sa.Text(), nullable=True),
    )


def downgrade():
    op.drop_column("session_summaries", "record_notes")
    op.drop_table("formal_records")
