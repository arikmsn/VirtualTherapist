"""Add scheduled message fields to messages table

Adds scheduling and channel fields needed for Messages Center v1 (Phase C).
New statuses (SCHEDULED, CANCELLED, FAILED) don't need a migration because
native_enum=False — they're just new string values.

Revision ID: 005_add_scheduled_message_fields
Revises: 004_add_twin_controls
Create Date: 2026-02-19
"""
from alembic import op
import sqlalchemy as sa

revision = "005_add_scheduled_message_fields"
down_revision = "004_add_twin_controls"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("messages", sa.Column("scheduled_send_at", sa.DateTime, nullable=True))
    op.add_column("messages", sa.Column("channel", sa.String(50), nullable=True, server_default="whatsapp"))
    op.add_column("messages", sa.Column("recipient_phone", sa.String(100), nullable=True))


def downgrade() -> None:
    op.drop_column("messages", "recipient_phone")
    op.drop_column("messages", "channel")
    op.drop_column("messages", "scheduled_send_at")
