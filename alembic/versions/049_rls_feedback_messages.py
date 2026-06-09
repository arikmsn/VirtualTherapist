"""Enable RLS on feedback_messages and revoke anon/authenticated grants.

Revision ID: 049
Revises: 048
Create Date: 2026-06-04

Security context
----------------
feedback_messages was created in migration 048 without RLS enabled.
The FastAPI backend connects via DATABASE_URL (superuser) which bypasses
RLS automatically — zero functional change to the backend.

The Supabase PostgREST Data API exposes every public table to the anon role
by default. Without RLS, anyone who obtained the anon key could read, write,
or delete feedback rows (therapist email + bug-report text).

Fix applied (matches the canonical "server-only" pattern on alembic_version,
apscheduler_jobs, modality_packs, ai_eval_runs, ai_eval_samples):

  1. ALTER TABLE … ENABLE ROW LEVEL SECURITY
     → non-superuser queries return zero rows (no policy = deny-all)

  2. REVOKE ALL … FROM anon / authenticated
     → defense-in-depth: removes the table-level GRANTs entirely so the
     role cannot even attempt a query (results in a permission error rather
     than an empty result set).

  service_role and the postgres superuser are unaffected by both changes.
"""

from alembic import op


def upgrade():
    # 1. Enable RLS — this alone is sufficient (no policy = deny-all)
    op.execute("ALTER TABLE public.feedback_messages ENABLE ROW LEVEL SECURITY;")

    # 2. Defense-in-depth: strip table-level GRANTs from client roles
    #    Superuser (DATABASE_URL) and service_role are unaffected.
    op.execute("REVOKE ALL ON TABLE public.feedback_messages FROM anon;")
    op.execute("REVOKE ALL ON TABLE public.feedback_messages FROM authenticated;")


def downgrade():
    # Re-grant (restores to the default Supabase "GRANT ALL" baseline)
    op.execute("GRANT ALL ON TABLE public.feedback_messages TO anon;")
    op.execute("GRANT ALL ON TABLE public.feedback_messages TO authenticated;")
    op.execute("ALTER TABLE public.feedback_messages DISABLE ROW LEVEL SECURITY;")
