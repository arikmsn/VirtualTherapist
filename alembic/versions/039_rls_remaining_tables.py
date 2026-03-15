"""Enable RLS on all remaining public tables not covered by migrations 013 and 027.

Supabase security advisor flags the following tables as lacking RLS:
  - ai_eval_runs
  - ai_eval_samples
  - ai_generation_log
  - audio_clips
  - deep_summaries
  - modality_packs
  - therapist_reference_vault
  - therapist_signature_profiles
  - treatment_plans

Also covers admin_alerts (added in migration 030, never had RLS).

What it does
------------
1. Enables RLS on all 10 flagged tables.
   service_role always bypasses RLS — no existing backend behaviour changes.

2. Creates per-therapist isolation policies for tables with a therapist_id column:
   - ai_generation_log         ALL  USING (therapist_id = current_therapist_id())
   - audio_clips               ALL  USING (therapist_id = current_therapist_id())
   - deep_summaries            ALL  USING (therapist_id = current_therapist_id())
   - therapist_reference_vault ALL  USING (therapist_id = current_therapist_id())
   - therapist_signature_profiles ALL USING (therapist_id = current_therapist_id())
   - treatment_plans           ALL  USING (therapist_id = current_therapist_id())
   - admin_alerts              ALL  USING (therapist_id = current_therapist_id())

3. No client-accessible policies for infrastructure/shared tables:
   - ai_eval_runs      — internal eval scaffolding; service_role only
   - ai_eval_samples   — internal eval scaffolding; service_role only
   - modality_packs    — shared reference data;    service_role only

   Enabling RLS with no policies causes every non-service_role query to return
   zero rows (the safe default).

Design notes
------------
- Does NOT use auth.uid() directly in policy bodies.  The existing helper
  public.current_therapist_id() (created by migration 013) wraps auth.uid()
  and returns the integer therapist PK.  All new policies delegate to it.
- backend DATABASE_URL is superuser → bypasses RLS → zero functional change.
- The Supabase Auth Admin API call in admin_panel.py uses the REST API with
  service_role bearer token — also unaffected by RLS.

Revision ID: 039
Revises: 038
Create Date: 2026-03-12
"""

from alembic import op
import sqlalchemy as sa

revision = "039"
down_revision = "038"
branch_labels = None
depends_on = None


def _is_supabase(bind) -> bool:
    """Return True only when running against a Supabase-flavoured PostgreSQL."""
    if bind.dialect.name != "postgresql":
        return False
    result = bind.execute(sa.text(
        "SELECT schema_name FROM information_schema.schemata WHERE schema_name = 'auth'"
    ))
    return result.fetchone() is not None


def upgrade() -> None:
    bind = op.get_bind()

    if not _is_supabase(bind):
        # SQLite (local dev) and plain PostgreSQL (no auth schema) skip silently.
        # RLS is a Supabase / PostgreSQL concept; no-op here is correct.
        return

    # ── 1. Enable RLS on all flagged tables ──────────────────────────────────
    tables = [
        "ai_eval_runs",
        "ai_eval_samples",
        "ai_generation_log",
        "audio_clips",
        "deep_summaries",
        "modality_packs",
        "therapist_reference_vault",
        "therapist_signature_profiles",
        "treatment_plans",
        "admin_alerts",
    ]
    for table in tables:
        bind.execute(sa.text(
            f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY"
        ))

    # ── 2. Per-therapist isolation policies ───────────────────────────────────
    # Pattern: ALL operations allowed only when therapist_id matches the
    # authenticated therapist.  service_role bypasses this automatically.

    # ai_generation_log — therapist_id is nullable (SET NULL on therapist delete).
    # Rows with therapist_id IS NULL will not match any authenticated therapist,
    # which is the correct behaviour (orphaned log rows are service_role only).
    bind.execute(sa.text("""
        CREATE POLICY "ai_generation_log_by_therapist"
        ON public.ai_generation_log
        FOR ALL
        USING (therapist_id = public.current_therapist_id());
    """))

    bind.execute(sa.text("""
        CREATE POLICY "audio_clips_by_therapist"
        ON public.audio_clips
        FOR ALL
        USING (therapist_id = public.current_therapist_id());
    """))

    bind.execute(sa.text("""
        CREATE POLICY "deep_summaries_by_therapist"
        ON public.deep_summaries
        FOR ALL
        USING (therapist_id = public.current_therapist_id());
    """))

    bind.execute(sa.text("""
        CREATE POLICY "therapist_reference_vault_by_therapist"
        ON public.therapist_reference_vault
        FOR ALL
        USING (therapist_id = public.current_therapist_id());
    """))

    bind.execute(sa.text("""
        CREATE POLICY "therapist_signature_profiles_by_therapist"
        ON public.therapist_signature_profiles
        FOR ALL
        USING (therapist_id = public.current_therapist_id());
    """))

    bind.execute(sa.text("""
        CREATE POLICY "treatment_plans_by_therapist"
        ON public.treatment_plans
        FOR ALL
        USING (therapist_id = public.current_therapist_id());
    """))

    # admin_alerts — therapist_id is nullable (alerts may be system-wide).
    # Therapists can only see alerts linked to their own account.
    # System-wide alerts (therapist_id IS NULL) are service_role only.
    bind.execute(sa.text("""
        CREATE POLICY "admin_alerts_by_therapist"
        ON public.admin_alerts
        FOR ALL
        USING (therapist_id = public.current_therapist_id());
    """))

    # ── 3. No client policies for infrastructure / shared-reference tables ────
    # ai_eval_runs, ai_eval_samples, modality_packs:
    # RLS enabled above; no policy added → non-service_role sees zero rows.
    # This is the safest default for internal tooling tables.


def downgrade() -> None:
    bind = op.get_bind()

    if not _is_supabase(bind):
        return

    policies = [
        ("ai_generation_log",            "ai_generation_log_by_therapist"),
        ("audio_clips",                  "audio_clips_by_therapist"),
        ("deep_summaries",               "deep_summaries_by_therapist"),
        ("therapist_reference_vault",    "therapist_reference_vault_by_therapist"),
        ("therapist_signature_profiles", "therapist_signature_profiles_by_therapist"),
        ("treatment_plans",              "treatment_plans_by_therapist"),
        ("admin_alerts",                 "admin_alerts_by_therapist"),
    ]
    for table, policy in policies:
        bind.execute(sa.text(
            f"DROP POLICY IF EXISTS {policy} ON public.{table}"
        ))

    tables = [
        "ai_eval_runs",
        "ai_eval_samples",
        "ai_generation_log",
        "audio_clips",
        "deep_summaries",
        "modality_packs",
        "therapist_reference_vault",
        "therapist_signature_profiles",
        "treatment_plans",
        "admin_alerts",
    ]
    for table in tables:
        bind.execute(sa.text(
            f"ALTER TABLE public.{table} DISABLE ROW LEVEL SECURITY"
        ))
