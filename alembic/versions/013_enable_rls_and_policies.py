"""Enable Row Level Security (RLS) on all public tables

This migration fixes two Supabase lint categories:
  - rls_disabled_in_public   (every table in public schema)
  - sensitive_columns_exposed (tables containing patient_id / PHI)

What it does
------------
1. Adds therapists.supabase_user_id (UUID, nullable, unique)
   This is the bridge between Supabase auth.users (UUID PKs) and our
   integer-PK therapist rows.  Populate it when Supabase Auth is wired
   for direct client access; NULL is fine for now because service_role
   bypasses RLS entirely.

2. Enables RLS on all 12 flagged tables.
   service_role always bypasses RLS — no existing backend behaviour changes.

3. Creates public.current_therapist_id() RETURNS integer
   A SECURITY DEFINER helper: maps auth.uid() → therapists.id (integer).
   All policies use this single function so ownership logic is centralised.

4. Creates per-table policies:
   - therapists            SELECT + UPDATE on own row (id = current_therapist_id())
   - therapist_profiles    ALL on therapist_id = current_therapist_id()
   - patients              ALL on therapist_id = current_therapist_id()
   - sessions              ALL on therapist_id = current_therapist_id()
   - session_summaries     ALL via EXISTS through sessions (no direct therapist_id)
   - messages              ALL on therapist_id = current_therapist_id()
   - patient_notes         ALL on therapist_id = current_therapist_id()
   - therapist_notes       ALL on therapist_id = current_therapist_id()
   - exercises             ALL on therapist_id = current_therapist_id()
   - audit_logs            SELECT on user_id = current_therapist_id()
                           (audit trail is immutable; backend writes via service_role)
   - apscheduler_jobs      RLS enabled, NO policies → service_role only
   - alembic_version       RLS enabled, NO policies → service_role only

5. Supabase API exposure (manual step after migration):
   In the Supabase Dashboard go to
     Settings → API → "Exposed schemas" or
     Table Editor → the table → "Realtime / PostgREST" toggle
   and un-expose apscheduler_jobs and alembic_version so they do not
   appear in the auto-generated REST API at all.

Schema assumptions documented here
-----------------------------------
- All therapist_id / patient_id FK columns are INTEGER (not UUID).
- session_summaries carries no therapist_id column; the relationship is
  sessions.summary_id → session_summaries.id, so ownership is resolved
  with an EXISTS subquery on sessions.
- audit_logs.user_id stores the therapist integer ID with no FK constraint.
- supabase_user_id is populated externally when Supabase Auth is enabled
  (e.g. from the Google OAuth flow or a Supabase Auth webhook).

Revision ID: 013
Revises: 012
Create Date: 2026-03-04
"""

from alembic import op
import sqlalchemy as sa

revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    # ── 1. Add supabase_user_id to therapists ─────────────────────────────
    # Nullable UUID column; populated when Supabase Auth is wired up.
    # Added for both PostgreSQL and SQLite so autogenerate stays consistent.
    op.add_column(
        "therapists",
        sa.Column(
            "supabase_user_id",
            sa.String(36),   # UUID stored as string; UUID type is PG-only
            nullable=True,
            unique=True,
        ),
    )

    if bind.dialect.name != "postgresql":
        # All remaining statements are PostgreSQL / Supabase-specific.
        # SQLite (local dev) skips them silently.
        return

    # ── 2. Enable RLS on every flagged table ──────────────────────────────
    tables_needing_rls = [
        "therapists",
        "therapist_profiles",
        "patients",
        "sessions",
        "session_summaries",
        "messages",
        "patient_notes",
        "therapist_notes",
        "exercises",
        "audit_logs",
        "apscheduler_jobs",
        "alembic_version",
    ]
    for table in tables_needing_rls:
        bind.execute(sa.text(
            f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY"
        ))

    # ── 3. Helper function: current_therapist_id() ────────────────────────
    # Returns the integer PK of the therapist whose supabase_user_id
    # matches the JWT subject from Supabase Auth (auth.uid()).
    # SECURITY DEFINER so it can query the therapists table even when the
    # calling role has restricted privileges.
    bind.execute(sa.text("""
        CREATE OR REPLACE FUNCTION public.current_therapist_id()
        RETURNS integer
        LANGUAGE sql
        STABLE
        SECURITY DEFINER
        SET search_path = public
        AS $$
            SELECT t.id
            FROM   public.therapists t
            WHERE  t.supabase_user_id = auth.uid()::text
            LIMIT  1;
        $$;
    """))

    # ── 4. RLS policies ───────────────────────────────────────────────────

    # therapists — therapist can read/update only their own row
    bind.execute(sa.text("""
        CREATE POLICY "therapist_select_own_row"
        ON public.therapists
        FOR SELECT
        USING (id = public.current_therapist_id());
    """))
    bind.execute(sa.text("""
        CREATE POLICY "therapist_update_own_row"
        ON public.therapists
        FOR UPDATE
        USING (id = public.current_therapist_id());
    """))

    # therapist_profiles
    bind.execute(sa.text("""
        CREATE POLICY "therapist_profiles_by_owner"
        ON public.therapist_profiles
        FOR ALL
        USING (therapist_id = public.current_therapist_id());
    """))

    # patients
    bind.execute(sa.text("""
        CREATE POLICY "patients_by_therapist"
        ON public.patients
        FOR ALL
        USING (therapist_id = public.current_therapist_id());
    """))

    # sessions
    bind.execute(sa.text("""
        CREATE POLICY "sessions_by_therapist"
        ON public.sessions
        FOR ALL
        USING (therapist_id = public.current_therapist_id());
    """))

    # session_summaries — no direct therapist_id; infer via sessions
    bind.execute(sa.text("""
        CREATE POLICY "session_summaries_by_therapist"
        ON public.session_summaries
        FOR ALL
        USING (
            EXISTS (
                SELECT 1
                FROM   public.sessions s
                WHERE  s.summary_id  = session_summaries.id
                  AND  s.therapist_id = public.current_therapist_id()
            )
        );
    """))

    # messages
    bind.execute(sa.text("""
        CREATE POLICY "messages_by_therapist"
        ON public.messages
        FOR ALL
        USING (therapist_id = public.current_therapist_id());
    """))

    # patient_notes
    bind.execute(sa.text("""
        CREATE POLICY "patient_notes_by_therapist"
        ON public.patient_notes
        FOR ALL
        USING (therapist_id = public.current_therapist_id());
    """))

    # therapist_notes
    bind.execute(sa.text("""
        CREATE POLICY "therapist_notes_by_therapist"
        ON public.therapist_notes
        FOR ALL
        USING (therapist_id = public.current_therapist_id());
    """))

    # exercises
    bind.execute(sa.text("""
        CREATE POLICY "exercises_by_therapist"
        ON public.exercises
        FOR ALL
        USING (therapist_id = public.current_therapist_id());
    """))

    # audit_logs — SELECT only; backend writes via service_role
    # user_id stores therapist integer ID (no FK, but same value)
    bind.execute(sa.text("""
        CREATE POLICY "audit_logs_by_therapist"
        ON public.audit_logs
        FOR SELECT
        USING (user_id = public.current_therapist_id());
    """))

    # apscheduler_jobs — infrastructure table; NO client policies
    # (service_role bypasses RLS; clients see nothing)

    # alembic_version — infrastructure table; NO client policies
    # (service_role bypasses RLS; clients see nothing)


def downgrade() -> None:
    bind = op.get_bind()

    if bind.dialect.name == "postgresql":
        # Drop policies (order doesn't matter)
        policies = [
            ("therapists",         "therapist_select_own_row"),
            ("therapists",         "therapist_update_own_row"),
            ("therapist_profiles", "therapist_profiles_by_owner"),
            ("patients",           "patients_by_therapist"),
            ("sessions",           "sessions_by_therapist"),
            ("session_summaries",  "session_summaries_by_therapist"),
            ("messages",           "messages_by_therapist"),
            ("patient_notes",      "patient_notes_by_therapist"),
            ("therapist_notes",    "therapist_notes_by_therapist"),
            ("exercises",          "exercises_by_therapist"),
            ("audit_logs",         "audit_logs_by_therapist"),
        ]
        for table, policy in policies:
            bind.execute(sa.text(
                f"DROP POLICY IF EXISTS {policy} ON public.{table}"
            ))

        bind.execute(sa.text(
            "DROP FUNCTION IF EXISTS public.current_therapist_id()"
        ))

        # Disable RLS (note: DISABLE does not drop the policies)
        tables_needing_rls = [
            "therapists", "therapist_profiles", "patients", "sessions",
            "session_summaries", "messages", "patient_notes", "therapist_notes",
            "exercises", "audit_logs", "apscheduler_jobs", "alembic_version",
        ]
        for table in tables_needing_rls:
            bind.execute(sa.text(
                f"ALTER TABLE public.{table} DISABLE ROW LEVEL SECURITY"
            ))

    # Remove supabase_user_id from therapists (both dialects)
    op.drop_column("therapists", "supabase_user_id")
