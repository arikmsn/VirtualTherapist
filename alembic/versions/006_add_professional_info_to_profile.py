"""Add professional info fields to therapist_profiles

Adds education, certifications, years_of_experience, and areas_of_expertise
to the TherapistProfile table for Twin Profile display and AI prompt injection.

Revision ID: 006_add_professional_info_to_profile
Revises: 005_add_scheduled_message_fields
Create Date: 2026-02-19
"""
from alembic import op
import sqlalchemy as sa

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("therapist_profiles", sa.Column("education", sa.Text, nullable=True))
    op.add_column("therapist_profiles", sa.Column("certifications", sa.Text, nullable=True))
    op.add_column("therapist_profiles", sa.Column("years_of_experience", sa.String(50), nullable=True))
    op.add_column("therapist_profiles", sa.Column("areas_of_expertise", sa.Text, nullable=True))


def downgrade() -> None:
    op.drop_column("therapist_profiles", "areas_of_expertise")
    op.drop_column("therapist_profiles", "years_of_experience")
    op.drop_column("therapist_profiles", "certifications")
    op.drop_column("therapist_profiles", "education")
