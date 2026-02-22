"""Add Twin v0.1 control fields to therapist_profiles

Revision ID: 004_add_twin_controls
Revises: 003_add_transcript_to_summaries
Create Date: 2026-02-18
"""
from alembic import op
import sqlalchemy as sa

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("therapist_profiles", sa.Column("tone_warmth", sa.Integer, nullable=True, server_default="3"))
    op.add_column("therapist_profiles", sa.Column("directiveness", sa.Integer, nullable=True, server_default="3"))
    op.add_column("therapist_profiles", sa.Column("prohibitions", sa.JSON, nullable=True))
    op.add_column("therapist_profiles", sa.Column("custom_rules", sa.Text, nullable=True))
    op.add_column("therapist_profiles", sa.Column("style_version", sa.Integer, nullable=True, server_default="1"))


def downgrade() -> None:
    op.drop_column("therapist_profiles", "style_version")
    op.drop_column("therapist_profiles", "custom_rules")
    op.drop_column("therapist_profiles", "prohibitions")
    op.drop_column("therapist_profiles", "directiveness")
    op.drop_column("therapist_profiles", "tone_warmth")
