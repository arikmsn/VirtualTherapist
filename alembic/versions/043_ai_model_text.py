"""Widen session_summaries.ai_model from VARCHAR(200) to TEXT

Preventive hardening: model identifiers sourced from the Anthropic API
could exceed 200 chars if versioning suffixes are added. TEXT removes
the constraint without changing any application logic.

Revision ID: 043
Revises: 042
Create Date: 2026-04-29
"""
from alembic import op
import sqlalchemy as sa

revision = "043"
down_revision = "042"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "session_summaries",
        "ai_model",
        type_=sa.Text(),
        existing_nullable=True,
    )


def downgrade():
    op.alter_column(
        "session_summaries",
        "ai_model",
        type_=sa.String(200),
        existing_nullable=True,
    )
