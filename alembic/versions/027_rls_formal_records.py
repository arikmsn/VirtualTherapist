"""Enable RLS on public.formal_records and add per-therapist isolation policy.

formal_records was created in migration 018, after the bulk RLS migration (013),
so it was never covered.  This migration brings it in line with all other
patient-data tables.

What it does
------------
1. Enables RLS on public.formal_records.
   service_role bypasses RLS -- no backend behaviour changes.

2. Creates one policy:
   formal_records_by_therapist  ALL  USING (therapist_id = public.current_therapist_id())
   Mirrors the identical pattern on patients, messages, exercises, etc.

Revision ID: 027
Revises: 026
Create Date: 2026-03-07
"""

from alembic import op
import sqlalchemy as sa

revision = "027"
down_revision = "026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    if bind.dialect.name != "postgresql":
        # SQLite (local dev) -- RLS is a PostgreSQL/Supabase concept; skip silently.
        return

    # Detect Supabase (auth schema present).  On plain PostgreSQL (Render) the
    # auth.uid() function does not exist, so policies cannot be created.
    result = bind.execute(sa.text(
        "SELECT schema_name FROM information_schema.schemata WHERE schema_name = 'auth'"
    ))
    if result.fetchone() is None:
        return

    # 1. Enable RLS
    bind.execute(sa.text(
        "ALTER TABLE public.formal_records ENABLE ROW LEVEL SECURITY"
    ))

    # 2. Per-therapist isolation -- mirrors the pattern from migration 013
    bind.execute(sa.text("""
        CREATE POLICY "formal_records_by_therapist"
        ON public.formal_records
        FOR ALL
        USING (therapist_id = public.current_therapist_id());
    """))


def downgrade() -> None:
    bind = op.get_bind()

    if bind.dialect.name != "postgresql":
        return

    result = bind.execute(sa.text(
        "SELECT schema_name FROM information_schema.schemata WHERE schema_name = 'auth'"
    ))
    if result.fetchone() is None:
        return

    bind.execute(sa.text(
        "DROP POLICY IF EXISTS formal_records_by_therapist ON public.formal_records"
    ))
    bind.execute(sa.text(
        "ALTER TABLE public.formal_records DISABLE ROW LEVEL SECURITY"
    ))
