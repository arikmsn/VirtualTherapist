"""Fix PostgreSQL compatibility: convert native ENUM columns to VARCHAR

Migration 001 created native PostgreSQL ENUM types for 5 columns, but
every SQLAlchemy model uses native_enum=False (VARCHAR storage).  When
psycopg2 sends a plain string for an INSERT into a native ENUM column
PostgreSQL raises a type-adaptation error, causing 500s on every write
endpoint (POST /patients, POST /sessions, POST /messages, onboarding).

This migration:
  1. Converts the 5 affected columns from their native ENUM type to
     VARCHAR(50) using USING col::text  (data is preserved as-is).
  2. Drops the now-unused native ENUM types.
  3. Adds server_default to boolean/integer columns that previously only
     had Python-side defaults — ensures non-NULL values even for raw
     inserts and prevents Pydantic validation errors after db.refresh().

Safe for re-runs: IF NOT EXISTS / IF EXISTS guards throughout.
PostgreSQL-only: SQLite (dev) already stores enums as VARCHAR, no DDL
needed there.

Revision ID: 009
Revises: 008
Create Date: 2026-02-23
"""
from alembic import op
import sqlalchemy as sa

revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    if bind.dialect.name == "postgresql":
        # ── 1. Convert native ENUM columns → VARCHAR ──────────────────────
        # patients.status  (patientstatus)
        bind.execute(sa.text(
            "ALTER TABLE patients "
            "ALTER COLUMN status TYPE VARCHAR(50) USING status::text"
        ))
        # sessions.session_type  (sessiontype)
        bind.execute(sa.text(
            "ALTER TABLE sessions "
            "ALTER COLUMN session_type TYPE VARCHAR(50) USING session_type::text"
        ))
        # messages.status + messages.direction  (messagestatus, messagedirection)
        bind.execute(sa.text(
            "ALTER TABLE messages "
            "ALTER COLUMN status TYPE VARCHAR(50) USING status::text, "
            "ALTER COLUMN direction TYPE VARCHAR(50) USING direction::text"
        ))
        # therapist_profiles.therapeutic_approach  (therapeuticapproach)
        bind.execute(sa.text(
            "ALTER TABLE therapist_profiles "
            "ALTER COLUMN therapeutic_approach TYPE VARCHAR(50) "
            "USING therapeutic_approach::text"
        ))

        # ── 2. Drop the native ENUM types (no longer referenced) ──────────
        # Drop in dependency order; IF EXISTS makes it idempotent.
        bind.execute(sa.text("DROP TYPE IF EXISTS messagestatus"))
        bind.execute(sa.text("DROP TYPE IF EXISTS messagedirection"))
        bind.execute(sa.text("DROP TYPE IF EXISTS patientstatus"))
        bind.execute(sa.text("DROP TYPE IF EXISTS sessiontype"))
        bind.execute(sa.text("DROP TYPE IF EXISTS therapeuticapproach"))

    # ── 3. Add server_defaults (applies to both PostgreSQL and SQLite) ────
    # These ensure non-NULL values even on raw inserts and prevent
    # Pydantic validation errors when ORM refresh reads back NULL.

    # therapists
    op.alter_column("therapists", "is_active",
                    server_default=sa.text("true"), existing_type=sa.Boolean())
    op.alter_column("therapists", "is_verified",
                    server_default=sa.text("false"), existing_type=sa.Boolean())

    # therapist_profiles
    op.alter_column("therapist_profiles", "onboarding_completed",
                    server_default=sa.text("false"), existing_type=sa.Boolean())
    op.alter_column("therapist_profiles", "onboarding_step",
                    server_default=sa.text("0"), existing_type=sa.Integer())
    op.alter_column("therapist_profiles", "tone_warmth",
                    server_default=sa.text("3"), existing_type=sa.Integer())
    op.alter_column("therapist_profiles", "directiveness",
                    server_default=sa.text("3"), existing_type=sa.Integer())
    op.alter_column("therapist_profiles", "style_version",
                    server_default=sa.text("1"), existing_type=sa.Integer())

    # patients
    op.alter_column("patients", "status",
                    server_default=sa.text("'active'"), existing_type=sa.String(50))
    op.alter_column("patients", "allow_ai_contact",
                    server_default=sa.text("true"), existing_type=sa.Boolean())
    op.alter_column("patients", "completed_exercises_count",
                    server_default=sa.text("0"), existing_type=sa.Integer())
    op.alter_column("patients", "missed_exercises_count",
                    server_default=sa.text("0"), existing_type=sa.Integer())

    # sessions
    op.alter_column("sessions", "session_type",
                    server_default=sa.text("'individual'"), existing_type=sa.String(50))
    op.alter_column("sessions", "has_recording",
                    server_default=sa.text("false"), existing_type=sa.Boolean())

    # session_summaries
    op.alter_column("session_summaries", "therapist_edited",
                    server_default=sa.text("false"), existing_type=sa.Boolean())
    op.alter_column("session_summaries", "approved_by_therapist",
                    server_default=sa.text("false"), existing_type=sa.Boolean())

    # messages
    op.alter_column("messages", "status",
                    server_default=sa.text("'draft'"), existing_type=sa.String(50))
    op.alter_column("messages", "requires_approval",
                    server_default=sa.text("true"), existing_type=sa.Boolean())
    op.alter_column("messages", "generated_by_ai",
                    server_default=sa.text("true"), existing_type=sa.Boolean())


def downgrade() -> None:
    # Removing server_defaults and re-adding native ENUMs is impractical
    # for a running production database.  Downgrade is intentionally a no-op.
    pass
