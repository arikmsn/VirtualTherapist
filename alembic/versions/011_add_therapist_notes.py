"""Add therapist_notes table for global side notebook

Revision ID: 011_add_therapist_notes
Revises: 010_add_patient_notes
Create Date: 2026-02-23
"""

from alembic import op
import sqlalchemy as sa

revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "therapist_notes",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("therapist_id", sa.Integer, sa.ForeignKey("therapists.id"), nullable=False, index=True),
        sa.Column("title", sa.String(255), nullable=True),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("tags", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("therapist_notes")
