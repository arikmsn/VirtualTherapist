"""Add start_time, end_time to sessions and status to session_summaries

Revision ID: 002_add_session_time_and_summary_status
Revises: 001_initial_schema
Create Date: 2026-02-18
"""
from alembic import op
import sqlalchemy as sa


revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None

SUMMARY_STATUS_VALUES = ("draft", "approved")


def upgrade() -> None:
    op.add_column("sessions", sa.Column("start_time", sa.DateTime, nullable=True))
    op.add_column("sessions", sa.Column("end_time", sa.DateTime, nullable=True))
    op.add_column(
        "session_summaries",
        sa.Column(
            "status",
            sa.Enum(*SUMMARY_STATUS_VALUES, name="summarystatus", native_enum=False),
            nullable=False,
            server_default="draft",
        ),
    )


def downgrade() -> None:
    op.drop_column("session_summaries", "status")
    op.drop_column("sessions", "end_time")
    op.drop_column("sessions", "start_time")
