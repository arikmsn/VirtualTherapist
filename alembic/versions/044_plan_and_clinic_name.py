"""Add plan and clinic_name columns to therapists

Revision ID: 044
Revises: 043
Create Date: 2026-05-10

plan: authoritative plan label (free/pro/clinic). Replaces intended_plan for display purposes.
      Existing rows with intended_plan='pro' are migrated to plan='pro'; all others get 'free'.
clinic_name: optional clinic name shown when plan='clinic'.
"""

from alembic import op
import sqlalchemy as sa

revision = '044'
down_revision = '043'
branch_labels = None
depends_on = None


def upgrade():
    # PostgreSQL
    try:
        op.add_column('therapists', sa.Column('plan', sa.String(50), nullable=False, server_default='free'))
        op.add_column('therapists', sa.Column('clinic_name', sa.Text(), nullable=True))
        # Migrate existing marketing attribution to real plan
        op.execute("UPDATE therapists SET plan = 'pro' WHERE intended_plan = 'pro'")
    except Exception:
        # SQLite fallback (development)
        try:
            with op.batch_alter_table('therapists') as batch_op:
                batch_op.add_column(sa.Column('plan', sa.String(50), nullable=False, server_default='free'))
                batch_op.add_column(sa.Column('clinic_name', sa.Text(), nullable=True))
            op.execute("UPDATE therapists SET plan = 'pro' WHERE intended_plan = 'pro'")
        except Exception:
            pass


def downgrade():
    try:
        op.drop_column('therapists', 'clinic_name')
        op.drop_column('therapists', 'plan')
    except Exception:
        try:
            with op.batch_alter_table('therapists') as batch_op:
                batch_op.drop_column('clinic_name')
                batch_op.drop_column('plan')
        except Exception:
            pass
