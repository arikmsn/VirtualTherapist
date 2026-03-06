"""Add prep_rendered_text to sessions for cache completeness

Revision ID: 024
Revises: 023
Create Date: 2026-03-06

Without this column, the 10-minute prep cache returned rendered_text=None,
forcing the UI to show nothing even on a cache hit. Now we store the rendered
Hebrew prose alongside prep_json so the cache can serve the full response.
"""

from alembic import op
import sqlalchemy as sa

revision = "024"
down_revision = "023"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "sessions",
        sa.Column("prep_rendered_text", sa.Text, nullable=True),
    )


def downgrade():
    op.drop_column("sessions", "prep_rendered_text")
