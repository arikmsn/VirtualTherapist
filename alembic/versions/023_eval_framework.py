"""Phase 10 — Evaluation Framework: eval runs, eval samples, therapist ratings

Revision ID: 023
Revises: 022
Create Date: 2026-03-06
"""

from alembic import op
import sqlalchemy as sa

revision = "023"
down_revision = "022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── ai_eval_runs ──────────────────────────────────────────────────────────
    op.create_table(
        "ai_eval_runs",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("run_type", sa.String(64), nullable=True),
        sa.Column("flow_type", sa.String(64), nullable=True),
        sa.Column("triggered_by", sa.String(32), nullable=True),   # 'manual'|'scheduled'|'deploy'
        sa.Column("model_used", sa.String(128), nullable=True),
        sa.Column("sample_size", sa.Integer, nullable=True),
        sa.Column("mean_completeness", sa.Float, nullable=True),
        sa.Column("mean_confidence", sa.Float, nullable=True),
        sa.Column("mean_edit_distance", sa.Float, nullable=True),
        sa.Column("mean_therapist_rating", sa.Float, nullable=True),
        sa.Column("regression_detected", sa.Boolean, server_default="0", nullable=True),
        sa.Column("regression_details", sa.JSON, nullable=True),
        sa.Column("passed", sa.Boolean, nullable=True),
        sa.Column("run_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
        sa.Column("duration_ms", sa.Integer, nullable=True),
    )

    # ── ai_eval_samples ───────────────────────────────────────────────────────
    op.create_table(
        "ai_eval_samples",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("eval_run_id", sa.Integer, sa.ForeignKey("ai_eval_runs.id"), nullable=True),
        sa.Column("session_id", sa.Integer, nullable=True),
        sa.Column("flow_type", sa.String(64), nullable=True),
        sa.Column("input_hash", sa.String(64), nullable=True),   # SHA256 of input
        sa.Column("output_text", sa.Text, nullable=True),
        sa.Column("completeness_score", sa.Float, nullable=True),
        sa.Column("confidence", sa.Float, nullable=True),
        sa.Column("edit_distance", sa.Integer, nullable=True),
        sa.Column("passed", sa.Boolean, nullable=True),
        sa.Column("failure_reason", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
    )

    # ── session_summaries: therapist rating fields ────────────────────────────
    op.add_column(
        "session_summaries",
        sa.Column("therapist_rating", sa.Integer, nullable=True),          # 1-5
    )
    op.add_column(
        "session_summaries",
        sa.Column("therapist_rating_comment", sa.Text, nullable=True),
    )
    op.add_column(
        "session_summaries",
        sa.Column("rated_at", sa.DateTime, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("session_summaries", "rated_at")
    op.drop_column("session_summaries", "therapist_rating_comment")
    op.drop_column("session_summaries", "therapist_rating")
    op.drop_table("ai_eval_samples")
    op.drop_table("ai_eval_runs")
