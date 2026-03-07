"""Add audio_clips table for multi-clip session recordings

Revision ID: 026
Revises: 025
Create Date: 2026-03-06
"""

from alembic import op
import sqlalchemy as sa

revision = "026"
down_revision = "025"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "audio_clips",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("session_id", sa.Integer, sa.ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("therapist_id", sa.Integer, sa.ForeignKey("therapists.id", ondelete="CASCADE"), nullable=False),
        sa.Column("clip_index", sa.Integer, nullable=False),
        sa.Column("duration_seconds", sa.Integer, nullable=True),
        sa.Column("transcript", sa.Text, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=True),
        sa.Column("updated_at", sa.DateTime, nullable=True),
    )


def downgrade():
    op.drop_table("audio_clips")
