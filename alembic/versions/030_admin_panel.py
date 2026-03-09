"""Add admin panel: therapist admin columns + admin_alerts table

Revision ID: 030
Revises: 029
Create Date: 2026-03-09

Adds:
- therapists.is_admin         — BOOLEAN DEFAULT FALSE
- therapists.is_blocked       — BOOLEAN DEFAULT FALSE
- therapists.last_login       — DATETIME nullable

Creates:
- admin_alerts table (id, alert_type, message, therapist_id, is_read, created_at)
"""

from alembic import op
import sqlalchemy as sa

revision = "030"
down_revision = "029"
branch_labels = None
depends_on = None


def upgrade():
    # Add admin columns to therapists
    with op.batch_alter_table("therapists") as batch_op:
        batch_op.add_column(sa.Column("is_admin", sa.Boolean(), server_default="0", nullable=False))
        batch_op.add_column(sa.Column("is_blocked", sa.Boolean(), server_default="0", nullable=False))
        batch_op.add_column(sa.Column("last_login", sa.DateTime(), nullable=True))

    # Create admin_alerts table
    op.create_table(
        "admin_alerts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("alert_type", sa.String(64), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("therapist_id", sa.Integer(), sa.ForeignKey("therapists.id", ondelete="SET NULL"), nullable=True),
        sa.Column("is_read", sa.Boolean(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )


def downgrade():
    op.drop_table("admin_alerts")
    with op.batch_alter_table("therapists") as batch_op:
        batch_op.drop_column("last_login")
        batch_op.drop_column("is_blocked")
        batch_op.drop_column("is_admin")
