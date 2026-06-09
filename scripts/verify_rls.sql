-- =============================================================================
-- RLS Verification Script — TherapyCompanion.AI
-- =============================================================================
-- Run this in the Supabase SQL Editor (or via psql as superuser) after applying
-- migrations 013, 027, and 039.
--
-- Section 1: Verify RLS is enabled on every expected table
-- Section 2: Verify expected policies exist
-- Section 3: Verify that anon/authenticated roles are denied access
-- Section 4: Verify that superuser can still read data
-- =============================================================================


-- ── Section 1: RLS enabled status ────────────────────────────────────────────
-- Expected: rowsecurity = TRUE for all 25 tables below.
-- Any row with rowsecurity = FALSE means RLS is missing on that table.

SELECT
    tablename,
    rowsecurity AS rls_enabled
FROM
    pg_tables
WHERE
    schemaname = 'public'
    AND tablename IN (
        -- Migration 013 tables
        'therapists', 'therapist_profiles', 'patients', 'sessions',
        'session_summaries', 'messages', 'patient_notes', 'therapist_notes',
        'exercises', 'audit_logs', 'apscheduler_jobs', 'alembic_version',
        -- Migration 027 table
        'formal_records',
        -- Migration 039 tables
        'ai_eval_runs', 'ai_eval_samples', 'ai_generation_log',
        'audio_clips', 'deep_summaries', 'modality_packs',
        'therapist_reference_vault', 'therapist_signature_profiles',
        'treatment_plans', 'admin_alerts'
    )
ORDER BY
    tablename;


-- ── Section 2: Expected policies ─────────────────────────────────────────────
-- Expected: one row per policy listed below.
-- Missing rows indicate a policy was not created.

SELECT
    tablename,
    policyname,
    cmd,
    qual
FROM
    pg_policies
WHERE
    schemaname = 'public'
    AND tablename IN (
        'ai_generation_log', 'audio_clips', 'deep_summaries',
        'therapist_reference_vault', 'therapist_signature_profiles',
        'treatment_plans', 'admin_alerts'
    )
ORDER BY
    tablename, policyname;

-- Expected policy names:
--   ai_generation_log            → ai_generation_log_by_therapist
--   audio_clips                  → audio_clips_by_therapist
--   deep_summaries               → deep_summaries_by_therapist
--   therapist_reference_vault    → therapist_reference_vault_by_therapist
--   therapist_signature_profiles → therapist_signature_profiles_by_therapist
--   treatment_plans              → treatment_plans_by_therapist
--   admin_alerts                 → admin_alerts_by_therapist

-- Infra tables with NO policies (RLS enabled, blocks all non-service_role):
SELECT
    tablename,
    COUNT(policyname) AS policy_count
FROM
    pg_policies
WHERE
    schemaname = 'public'
    AND tablename IN ('ai_eval_runs', 'ai_eval_samples', 'modality_packs')
GROUP BY
    tablename;
-- Expected: 0 rows returned (no policies on these tables).
-- If any row appears, unexpected policies were added — investigate.


-- ── Section 3: Anon / authenticated role is denied ───────────────────────────
-- Run each SET ROLE block to simulate a client with no Supabase JWT.
-- Every SELECT should return 0 rows (not an error — RLS just filters everything).

SET ROLE anon;
SELECT COUNT(*) AS anon_can_see_deep_summaries FROM public.deep_summaries;
-- Expected: 0

SELECT COUNT(*) AS anon_can_see_treatment_plans FROM public.treatment_plans;
-- Expected: 0

SELECT COUNT(*) AS anon_can_see_audio_clips FROM public.audio_clips;
-- Expected: 0

SELECT COUNT(*) AS anon_can_see_ai_eval_runs FROM public.ai_eval_runs;
-- Expected: 0

SELECT COUNT(*) AS anon_can_see_modality_packs FROM public.modality_packs;
-- Expected: 0

RESET ROLE;

-- Repeat for the 'authenticated' role (non-matching JWT, no therapist row):
SET ROLE authenticated;
SELECT COUNT(*) AS authenticated_can_see_deep_summaries FROM public.deep_summaries;
-- Expected: 0 (current_therapist_id() returns NULL with no matching supabase_user_id)

RESET ROLE;


-- ── Section 4: Superuser / service_role bypasses RLS ─────────────────────────
-- Running as postgres superuser (the normal state for the FastAPI backend).
-- These should return actual row counts from your data.

SELECT COUNT(*) AS superuser_deep_summaries   FROM public.deep_summaries;
SELECT COUNT(*) AS superuser_treatment_plans   FROM public.treatment_plans;
SELECT COUNT(*) AS superuser_audio_clips       FROM public.audio_clips;
SELECT COUNT(*) AS superuser_ai_generation_log FROM public.ai_generation_log;
SELECT COUNT(*) AS superuser_modality_packs    FROM public.modality_packs;
-- Expected: actual data counts (not necessarily 0)
-- If these also return 0, check that you are running as superuser, not anon.


-- ── Section 5: Alembic version sanity check ──────────────────────────────────
-- Confirm the migration chain is at head in production.

SELECT version_num FROM alembic_version;
-- Expected: latest migration number (048 as of 2026-06-04)


-- ── Section 6: feedback_messages — added 2026-06-04 (migration 049_rls_feedback_messages) ──
-- This table is server-only; verify RLS is on and anon/authenticated have no grants.

SELECT relname, relrowsecurity
FROM   pg_class
WHERE  relname = 'feedback_messages'
  AND  relnamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'public');
-- Expected: relrowsecurity = TRUE

SELECT grantee, privilege_type
FROM   information_schema.role_table_grants
WHERE  table_schema = 'public'
  AND  table_name   = 'feedback_messages'
  AND  grantee IN ('anon', 'authenticated');
-- Expected: 0 rows (grants revoked)

-- Anon attempt — should return 0 rows:
SET ROLE anon;
SELECT COUNT(*) AS anon_can_see_feedback FROM public.feedback_messages;
-- Expected: 0
RESET ROLE;
