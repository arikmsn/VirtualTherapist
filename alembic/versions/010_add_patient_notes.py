"""Add patient_notes table for therapist notebook feature

Revision ID: 010_add_patient_notes
Revises: 009_postgres_compat_enum_to_varchar
Create Date: 2026-02-23
"""

from alembic import op
import sqlalchemy as sa

revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "patient_notes",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("patient_id", sa.Integer, sa.ForeignKey("patients.id"), nullable=False, index=True),
        sa.Column("therapist_id", sa.Integer, sa.ForeignKey("therapists.id"), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("patient_notes")
