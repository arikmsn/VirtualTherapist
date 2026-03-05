"""Add completeness_score and completeness_data to session_summaries.

Revision ID: 015
Revises: 014
Create Date: 2026-03-06
"""

import sqlalchemy as sa
from alembic import op

revision = "015"
down_revision = "014"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "session_summaries",
        sa.Column("completeness_score", sa.Float(), nullable=True),
    )
    op.add_column(
        "session_summaries",
        sa.Column("completeness_data", sa.JSON(), nullable=True),
    )


def downgrade():
    op.drop_column("session_summaries", "completeness_data")
    op.drop_column("session_summaries", "completeness_score")
