"""Migration 021 — Deep summary table + extend therapist_reference_vault.

Phase 8: Deep Summary + Therapist Reference Vault.

Revision ID: 021
Revises: 020
Create Date: 2026-03-06
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "021"
down_revision = "020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Extend therapist_reference_vault ──────────────────────────────────────
    # Existing columns: id, therapist_id, title, content, tags,
    #                   modality_pack_ids, source_type, is_active,
    #                   created_at, updated_at
    op.add_column(
        "therapist_reference_vault",
        sa.Column(
            "client_id",
            sa.Integer,
            sa.ForeignKey("patients.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
    )
    op.add_column(
        "therapist_reference_vault",
        sa.Column("entry_type", sa.String(64), nullable=True),
    )
    op.add_column(
        "therapist_reference_vault",
        sa.Column("source_session_ids", sa.JSON, nullable=True),
    )
    op.add_column(
        "therapist_reference_vault",
        sa.Column("embedding_vector", sa.JSON, nullable=True),
    )
    op.add_column(
        "therapist_reference_vault",
        sa.Column("confidence", sa.Float, nullable=True),
    )

    # ── New table: deep_summaries ─────────────────────────────────────────────
    op.create_table(
        "deep_summaries",
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
        sa.Column("summary_json", sa.JSON, nullable=True),
        sa.Column("rendered_text", sa.Text, nullable=True),
        sa.Column("sessions_covered", sa.Integer, nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="draft"),
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


def downgrade() -> None:
    op.drop_table("deep_summaries")
    op.drop_column("therapist_reference_vault", "confidence")
    op.drop_column("therapist_reference_vault", "embedding_vector")
    op.drop_column("therapist_reference_vault", "source_session_ids")
    op.drop_column("therapist_reference_vault", "entry_type")
    op.drop_column("therapist_reference_vault", "client_id")
