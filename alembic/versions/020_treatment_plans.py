"""Migration 020 — Treatment plans table + drift columns on sessions.

Phase 7: Treatment Plan 2.0 + Plan Drift Helper.

Revision ID: 020
Revises: 019
Create Date: 2026-03-06
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "020"
down_revision = "019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── treatment_plans ───────────────────────────────────────────────────────
    op.create_table(
        "treatment_plans",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "patient_id",
            sa.Integer,
            sa.ForeignKey("patients.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "therapist_id",
            sa.Integer,
            sa.ForeignKey("therapists.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("plan_json", sa.JSON, nullable=True),
        sa.Column("rendered_text", sa.Text, nullable=True),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column(
            "parent_version_id",
            sa.Integer,
            sa.ForeignKey("treatment_plans.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("drift_score", sa.Float, nullable=True),
        sa.Column("drift_flags", sa.JSON, nullable=True),
        sa.Column("last_drift_check_at", sa.DateTime, nullable=True),
        sa.Column("approved_at", sa.DateTime, nullable=True),
        sa.Column("model_used", sa.String(128), nullable=True),
        sa.Column("tokens_used", sa.Integer, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )

    # ── sessions — drift check columns ────────────────────────────────────────
    op.add_column(
        "sessions",
        sa.Column("plan_drift_checked", sa.Boolean, nullable=True, server_default="0"),
    )
    op.add_column(
        "sessions",
        sa.Column("plan_drift_score", sa.Float, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("sessions", "plan_drift_score")
    op.drop_column("sessions", "plan_drift_checked")
    op.drop_table("treatment_plans")
