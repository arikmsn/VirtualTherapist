"""Add protocol columns to therapist_profiles and patients.

therapist_profiles:
  - protocols_used   JSON — list of protocol IDs the therapist uses globally
  - custom_protocols JSON — list of custom protocol dicts defined by this therapist

patients:
  - protocol_ids  JSON — protocol IDs selected for this specific patient
  - demographics  JSON — {age, marital_status, has_guardian, guardian_name, parent_name}

No new tables; all stored as JSON in existing rows.
"""

revision = "040"
down_revision = "039"

from alembic import op
import sqlalchemy as sa


def upgrade():
    # TherapistProfile — global protocol preferences
    op.add_column(
        "therapist_profiles",
        sa.Column("protocols_used", sa.JSON, nullable=True),
    )
    op.add_column(
        "therapist_profiles",
        sa.Column("custom_protocols", sa.JSON, nullable=True),
    )

    # Patient — per-patient protocol selection + demographics placeholder
    op.add_column(
        "patients",
        sa.Column("protocol_ids", sa.JSON, nullable=True),
    )
    op.add_column(
        "patients",
        sa.Column("demographics", sa.JSON, nullable=True),
    )


def downgrade():
    op.drop_column("therapist_profiles", "protocols_used")
    op.drop_column("therapist_profiles", "custom_protocols")
    op.drop_column("patients", "protocol_ids")
    op.drop_column("patients", "demographics")
