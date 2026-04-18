"""Add patient_limit column to therapists

Revision ID: 041
Revises: 040
Create Date: 2026-04-19
"""
from alembic import op
import sqlalchemy as sa

revision = "041"
down_revision = "040"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "therapists",
        sa.Column(
            "patient_limit",
            sa.Integer(),
            nullable=False,
            server_default="10",
        ),
    )


def downgrade():
    op.drop_column("therapists", "patient_limit")
