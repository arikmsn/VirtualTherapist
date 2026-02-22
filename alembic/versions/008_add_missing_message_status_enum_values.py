"""Add missing message status enum values for PostgreSQL

Migration 001 created the native PostgreSQL ENUM type `messagestatus`
with 8 values.  Messages Center v1 added SCHEDULED, CANCELLED, FAILED
to the Python MessageStatus enum but never added them to the PostgreSQL
type — causing INSERT/UPDATE failures when those statuses are written,
and potential type-mismatch errors on SELECT in some SQLAlchemy configs.

Revision ID: 008
Revises: 007
Create Date: 2026-02-23
"""
from alembic import op
import sqlalchemy as sa

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        # ALTER TYPE ADD VALUE cannot easily be rolled back in PostgreSQL,
        # but IF NOT EXISTS makes this idempotent on re-runs.
        bind.execute(sa.text("ALTER TYPE messagestatus ADD VALUE IF NOT EXISTS 'scheduled'"))
        bind.execute(sa.text("ALTER TYPE messagestatus ADD VALUE IF NOT EXISTS 'cancelled'"))
        bind.execute(sa.text("ALTER TYPE messagestatus ADD VALUE IF NOT EXISTS 'failed'"))
    # SQLite (dev): native_enum=False means status is VARCHAR — no DDL needed.


def downgrade() -> None:
    # PostgreSQL does not support removing values from a native ENUM type.
    pass
