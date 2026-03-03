"""Add google_sub and auth_provider to therapists table

Revision ID: 012_add_google_oauth_fields
Revises: 011
Create Date: 2026-03-03
"""

from alembic import op
import sqlalchemy as sa

revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "therapists",
        sa.Column("auth_provider", sa.String(50), nullable=True, server_default="email"),
    )
    op.add_column(
        "therapists",
        sa.Column("google_sub", sa.String(255), nullable=True),
    )
    op.create_index("ix_therapists_google_sub", "therapists", ["google_sub"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_therapists_google_sub", table_name="therapists")
    op.drop_column("therapists", "google_sub")
    op.drop_column("therapists", "auth_provider")
