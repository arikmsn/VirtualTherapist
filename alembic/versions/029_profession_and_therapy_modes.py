"""Add profession and primary_therapy_modes to therapist_profiles

Revision ID: 029
Revises: 028
Create Date: 2026-03-08

Adds:
- therapist_profiles.profession          — string, e.g. "psychologist"
- therapist_profiles.primary_therapy_modes — JSON array of strings, e.g. ["cbt", "dbt"]
"""

from alembic import op
import sqlalchemy as sa

revision = "029"
down_revision = "028"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("therapist_profiles") as batch_op:
        batch_op.add_column(sa.Column("profession", sa.String(100), nullable=True))
        batch_op.add_column(sa.Column("primary_therapy_modes", sa.JSON(), nullable=True))


def downgrade():
    with op.batch_alter_table("therapist_profiles") as batch_op:
        batch_op.drop_column("primary_therapy_modes")
        batch_op.drop_column("profession")
