"""Therapist Signature Engine 2.0 — extend therapist_signature_profiles.

Adds raw_samples storage, approved_sample_count, style_version, rebuild metadata,
and LLM-derived style fields needed to activate and inject the learned profile.

Revision ID: 019
Revises: 018
Create Date: 2026-03-06
"""

import sqlalchemy as sa
from alembic import op

revision = "019"
down_revision = "018"
branch_labels = None
depends_on = None


def upgrade():
    # Sample storage + counters
    op.add_column("therapist_signature_profiles",
                  sa.Column("approved_sample_count", sa.Integer(), server_default="0", nullable=False))
    op.add_column("therapist_signature_profiles",
                  sa.Column("min_samples_required", sa.Integer(), server_default="5", nullable=False))
    op.add_column("therapist_signature_profiles",
                  sa.Column("raw_samples", sa.JSON(), nullable=True))
    # Rebuild metadata
    op.add_column("therapist_signature_profiles",
                  sa.Column("last_updated_at", sa.DateTime(), nullable=True))
    op.add_column("therapist_signature_profiles",
                  sa.Column("style_version", sa.Integer(), server_default="1", nullable=False))
    # LLM-derived style fields (populated by rebuild_profile)
    op.add_column("therapist_signature_profiles",
                  sa.Column("style_summary", sa.Text(), nullable=True))
    op.add_column("therapist_signature_profiles",
                  sa.Column("style_examples", sa.JSON(), nullable=True))
    op.add_column("therapist_signature_profiles",
                  sa.Column("preferred_sentence_length", sa.String(20), nullable=True))
    op.add_column("therapist_signature_profiles",
                  sa.Column("preferred_voice", sa.String(20), nullable=True))
    op.add_column("therapist_signature_profiles",
                  sa.Column("uses_clinical_jargon", sa.Boolean(), nullable=True))


def downgrade():
    for col in [
        "uses_clinical_jargon", "preferred_voice", "preferred_sentence_length",
        "style_examples", "style_summary", "style_version", "last_updated_at",
        "raw_samples", "min_samples_required", "approved_sample_count",
    ]:
        op.drop_column("therapist_signature_profiles", col)
