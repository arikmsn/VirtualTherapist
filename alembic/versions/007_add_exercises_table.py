"""Add exercises table for homework / task tracking

Revision ID: 007_add_exercises_table
Revises: 006_add_professional_info_to_profile
Create Date: 2026-02-19
"""

from alembic import op
import sqlalchemy as sa

revision = "007_add_exercises_table"
down_revision = "006_add_professional_info_to_profile"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "exercises",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("patient_id", sa.Integer, sa.ForeignKey("patients.id"), nullable=False, index=True),
        sa.Column("therapist_id", sa.Integer, sa.ForeignKey("therapists.id"), nullable=False),
        sa.Column("session_summary_id", sa.Integer, sa.ForeignKey("session_summaries.id"), nullable=True),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("completed", sa.Boolean, nullable=False, server_default="0"),
        sa.Column("completed_at", sa.DateTime, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("exercises")
