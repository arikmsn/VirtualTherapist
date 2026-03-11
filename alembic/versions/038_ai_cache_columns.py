"""Add AI precompute cache columns to sessions and patients.

Revision ID: 038
Revises: 037
Create Date: 2026-03-11

sessions.prep_cache_valid_until — extended TTL for background-precomputed prep (7-day window).

patients.deep_summary_cache_* — stores the last precomputed deep summary result so that
  the next therapist-triggered generate can return instantly from cache without an LLM call.

patients.treatment_plan_cache_* — same pattern for treatment plans.

Session summary dedup uses the existing session_summaries.ai_input_fingerprint column
(already added in migration 025) — no new columns needed there.
"""

from alembic import op
import sqlalchemy as sa


revision = "038"
down_revision = "037"
branch_labels = None
depends_on = None


def _add_column_if_missing(conn, table: str, col: str, col_def: str) -> None:
    """Add a column only if it doesn't already exist (SQLite + PostgreSQL safe)."""
    if conn.dialect.name == "postgresql":
        conn.execute(sa.text(
            f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col} {col_def};"
        ))
    else:
        try:
            conn.execute(sa.text(
                f"ALTER TABLE {table} ADD COLUMN {col} {col_def};"
            ))
        except Exception:
            pass  # column already exists


def upgrade():
    conn = op.get_bind()

    # ── sessions ──────────────────────────────────────────────────────────────
    _add_column_if_missing(conn, "sessions", "prep_cache_valid_until", "TIMESTAMP DEFAULT NULL")

    # ── patients: deep summary cache ──────────────────────────────────────────
    _add_column_if_missing(conn, "patients", "deep_summary_cache_json",              "JSON DEFAULT NULL")
    _add_column_if_missing(conn, "patients", "deep_summary_cache_rendered_text",     "TEXT DEFAULT NULL")
    _add_column_if_missing(conn, "patients", "deep_summary_cache_fingerprint",       "TEXT DEFAULT NULL")
    _add_column_if_missing(conn, "patients", "deep_summary_cache_fingerprint_version", "INTEGER DEFAULT NULL")
    _add_column_if_missing(conn, "patients", "deep_summary_cache_valid_until",       "TIMESTAMP DEFAULT NULL")
    _add_column_if_missing(conn, "patients", "deep_summary_cache_sessions_covered",  "INTEGER DEFAULT NULL")
    _add_column_if_missing(conn, "patients", "deep_summary_cache_model_used",        "VARCHAR(200) DEFAULT NULL")

    # ── patients: treatment plan cache ────────────────────────────────────────
    _add_column_if_missing(conn, "patients", "treatment_plan_cache_json",              "JSON DEFAULT NULL")
    _add_column_if_missing(conn, "patients", "treatment_plan_cache_rendered_text",     "TEXT DEFAULT NULL")
    _add_column_if_missing(conn, "patients", "treatment_plan_cache_fingerprint",       "TEXT DEFAULT NULL")
    _add_column_if_missing(conn, "patients", "treatment_plan_cache_fingerprint_version", "INTEGER DEFAULT NULL")
    _add_column_if_missing(conn, "patients", "treatment_plan_cache_valid_until",       "TIMESTAMP DEFAULT NULL")
    _add_column_if_missing(conn, "patients", "treatment_plan_cache_model_used",        "VARCHAR(200) DEFAULT NULL")


def downgrade():
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        stmts = [
            "ALTER TABLE sessions DROP COLUMN IF EXISTS prep_cache_valid_until;",
            "ALTER TABLE patients DROP COLUMN IF EXISTS deep_summary_cache_json;",
            "ALTER TABLE patients DROP COLUMN IF EXISTS deep_summary_cache_rendered_text;",
            "ALTER TABLE patients DROP COLUMN IF EXISTS deep_summary_cache_fingerprint;",
            "ALTER TABLE patients DROP COLUMN IF EXISTS deep_summary_cache_fingerprint_version;",
            "ALTER TABLE patients DROP COLUMN IF EXISTS deep_summary_cache_valid_until;",
            "ALTER TABLE patients DROP COLUMN IF EXISTS deep_summary_cache_sessions_covered;",
            "ALTER TABLE patients DROP COLUMN IF EXISTS deep_summary_cache_model_used;",
            "ALTER TABLE patients DROP COLUMN IF EXISTS treatment_plan_cache_json;",
            "ALTER TABLE patients DROP COLUMN IF EXISTS treatment_plan_cache_rendered_text;",
            "ALTER TABLE patients DROP COLUMN IF EXISTS treatment_plan_cache_fingerprint;",
            "ALTER TABLE patients DROP COLUMN IF EXISTS treatment_plan_cache_fingerprint_version;",
            "ALTER TABLE patients DROP COLUMN IF EXISTS treatment_plan_cache_valid_until;",
            "ALTER TABLE patients DROP COLUMN IF EXISTS treatment_plan_cache_model_used;",
        ]
        for s in stmts:
            conn.execute(sa.text(s))
