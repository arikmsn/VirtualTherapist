"""
Tests for the precompute cache layer (migration 038 behaviour).

Covers:
- _precompute_to_cache return value (True=warmed, False=skip/fail)
- cache gate: both json AND rendered_text required for hit
- null pipeline result guard in generate_deep_summary
- precompute_prep_for_patient fallback to most-recent past session
"""
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.ai_cache import cache_valid_until, deep_summary_fingerprint, treatment_plan_fingerprint
from app.core.fingerprint import FINGERPRINT_VERSION


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_patient(
    *,
    ds_fp=None,
    ds_fp_ver=None,
    ds_valid_until=None,
    ds_json=None,
    ds_rendered=None,
    ds_sessions=None,
    ds_model=None,
    tp_fp=None,
    tp_fp_ver=None,
    tp_valid_until=None,
    tp_json=None,
    tp_rendered=None,
    tp_model=None,
):
    """Build a minimal Patient-like object for unit testing."""
    p = MagicMock()
    p.deep_summary_cache_fingerprint = ds_fp
    p.deep_summary_cache_fingerprint_version = ds_fp_ver
    p.deep_summary_cache_valid_until = ds_valid_until
    p.deep_summary_cache_json = ds_json
    p.deep_summary_cache_rendered_text = ds_rendered
    p.deep_summary_cache_sessions_covered = ds_sessions
    p.deep_summary_cache_model_used = ds_model
    p.treatment_plan_cache_fingerprint = tp_fp
    p.treatment_plan_cache_fingerprint_version = tp_fp_ver
    p.treatment_plan_cache_valid_until = tp_valid_until
    p.treatment_plan_cache_json = tp_json
    p.treatment_plan_cache_rendered_text = tp_rendered
    p.treatment_plan_cache_model_used = tp_model
    return p


def _approved_summaries(n: int) -> list[dict]:
    return [
        {
            "session_id": i,
            "session_date": f"2025-01-{i:02d}",
            "full_summary": f"Summary {i}",
            "topics_discussed": ["topic"],
            "next_session_plan": "plan",
            "risk_assessment": None,
            "mood_observed": None,
            "session_number": i,
            "homework_assigned": [],
        }
        for i in range(1, n + 1)
    ]


# ── DeepSummaryService._precompute_to_cache return value ─────────────────────

class TestDeepSummaryCacheReturnValue:
    """_precompute_to_cache should return True when cache is written, False otherwise."""

    def _make_db(self, patient, summaries):
        db = MagicMock()
        # query(Patient).filter(...).first() → patient
        db.query.return_value.filter.return_value.first.return_value = patient
        return db

    def _make_service(self, db, summaries):
        from app.services.deep_summary_service import DeepSummaryService
        svc = DeepSummaryService(db)
        svc._fetch_approved_summaries = MagicMock(return_value=summaries)
        svc._build_therapist_profile_dict = MagicMock(return_value={"modality": "cbt"})
        svc._get_active_plan_json = MagicMock(return_value=None)
        return svc

    @pytest.mark.asyncio
    async def test_returns_false_when_patient_not_found(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        from app.services.deep_summary_service import DeepSummaryService
        svc = DeepSummaryService(db)
        result = await svc._precompute_to_cache(
            patient_id=1, therapist_id=1, provider=MagicMock()
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_when_no_approved_summaries(self):
        patient = _make_patient()
        db = self._make_db(patient, [])
        svc = self._make_service(db, [])
        result = await svc._precompute_to_cache(
            patient_id=1, therapist_id=1, provider=MagicMock()
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_when_cache_still_valid(self):
        summaries = _approved_summaries(2)
        fp = deep_summary_fingerprint(summaries)
        patient = _make_patient(
            ds_fp=fp,
            ds_fp_ver=FINGERPRINT_VERSION,
            ds_valid_until=cache_valid_until(),  # fresh
            ds_json={"some": "data"},
            ds_rendered="some rendered text",
        )
        db = self._make_db(patient, summaries)
        svc = self._make_service(db, summaries)
        result = await svc._precompute_to_cache(
            patient_id=1, therapist_id=1, provider=MagicMock()
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_skips_when_json_present_but_rendered_text_null(self):
        """Cache must NOT be considered valid if rendered_text is None."""
        summaries = _approved_summaries(2)
        fp = deep_summary_fingerprint(summaries)
        patient = _make_patient(
            ds_fp=fp,
            ds_fp_ver=FINGERPRINT_VERSION,
            ds_valid_until=cache_valid_until(),
            ds_json={"arc_narrative": "some narrative with enough clinical content for validation"},
            ds_rendered=None,  # ← missing rendered_text should force re-run
        )
        db = self._make_db(patient, summaries)
        svc = self._make_service(db, summaries)

        # Make the pipeline return a valid result
        fake_result = MagicMock()
        fake_result.summary_json = {
            "arc_narrative": "refreshed narrative with enough clinical content for validation",
            "treatment_phases": [{"phase": "initial"}],
        }
        fake_result.rendered_text = "refreshed rendered text"
        fake_result.model_used = "claude-3"
        fake_result.tokens_used = 100

        with patch(
            "app.services.deep_summary_service.DeepSummaryPipeline"
        ) as MockPipeline, patch(
            "app.services.deep_summary_service.SignatureEngine"
        ) as MockSig, patch(
            "app.ai.deep_summary.VaultRetriever"
        ):
            MockPipeline.return_value.run = AsyncMock(return_value=fake_result)
            MockSig.return_value.get_active_profile = AsyncMock(return_value=None)
            svc._build_therapist_profile_dict = MagicMock(return_value={"modality": "cbt"})
            svc._get_active_plan_json = MagicMock(return_value=None)
            # VaultRetriever inside the service
            with patch(
                "app.services.deep_summary_service.VaultRetriever"
            ) as MockVR:
                MockVR.return_value.get_relevant_entries = AsyncMock(return_value=[])
                result = await svc._precompute_to_cache(
                    patient_id=1, therapist_id=1, provider=MagicMock()
                )

        assert result is True
        assert patient.deep_summary_cache_rendered_text == "refreshed rendered text"


# ── TreatmentPlanService._precompute_to_cache return value ───────────────────

class TestTreatmentPlanCacheReturnValue:

    def _make_db(self, patient, summaries):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = patient
        db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None
        return db

    def _make_service(self, db, summaries):
        from app.services.treatment_plan_service import TreatmentPlanService
        svc = TreatmentPlanService(db)
        svc._fetch_approved_summaries = MagicMock(return_value=summaries)
        svc._build_therapist_profile_dict = MagicMock(return_value={"modality": "cbt"})
        return svc

    @pytest.mark.asyncio
    async def test_returns_false_when_patient_not_found(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        from app.services.treatment_plan_service import TreatmentPlanService
        svc = TreatmentPlanService(db)
        result = await svc._precompute_to_cache(
            patient_id=1, therapist_id=1, provider=MagicMock()
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_when_cache_valid_with_both_fields(self):
        summaries = _approved_summaries(3)
        fp = treatment_plan_fingerprint(summaries)
        patient = _make_patient(
            tp_fp=fp,
            tp_fp_ver=FINGERPRINT_VERSION,
            tp_valid_until=cache_valid_until(),
            tp_json={"goals": []},
            tp_rendered="rendered plan",
        )
        db = self._make_db(patient, summaries)
        svc = self._make_service(db, summaries)
        result = await svc._precompute_to_cache(
            patient_id=1, therapist_id=1, provider=MagicMock()
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_skips_cache_when_rendered_text_missing(self):
        """Treatment plan cache is not valid if rendered_text is None."""
        summaries = _approved_summaries(2)
        fp = treatment_plan_fingerprint(summaries)
        patient = _make_patient(
            tp_fp=fp,
            tp_fp_ver=FINGERPRINT_VERSION,
            tp_valid_until=cache_valid_until(),
            tp_json={"primary_goals": [{"description": "goal 1"}]},
            tp_rendered=None,  # ← missing
        )
        db = self._make_db(patient, summaries)
        svc = self._make_service(db, summaries)

        fake_result = MagicMock()
        fake_result.plan_json = {"primary_goals": [{"description": "updated goal"}]}
        fake_result.rendered_text = "updated plan text with enough content to pass validation checks"
        fake_result.model_used = "claude-3"
        fake_result.tokens_used = 50

        with patch(
            "app.services.treatment_plan_service.TreatmentPlanPipeline"
        ) as MockPipeline, patch(
            "app.services.treatment_plan_service.SignatureEngine"
        ) as MockSig:
            MockPipeline.return_value.run = AsyncMock(return_value=fake_result)
            MockSig.return_value.get_active_profile = AsyncMock(return_value=None)
            result = await svc._precompute_to_cache(
                patient_id=1, therapist_id=1, provider=MagicMock()
            )

        assert result is True
        assert patient.treatment_plan_cache_rendered_text == "updated plan text with enough content to pass validation checks"


# ── generate_deep_summary: null pipeline guard ────────────────────────────────

class TestDeepSummaryNullGuard:
    """generate_deep_summary should raise ValueError if pipeline returns empty summary_json."""

    @pytest.mark.asyncio
    async def test_raises_if_summary_json_is_none(self):
        from app.services.deep_summary_service import DeepSummaryService

        summaries = _approved_summaries(2)
        patient = _make_patient()
        patient.id = 1

        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = patient

        svc = DeepSummaryService(db)
        svc._fetch_approved_summaries = MagicMock(return_value=summaries)
        svc._build_therapist_profile_dict = MagicMock(return_value={"modality": "cbt"})
        svc._get_active_plan_json = MagicMock(return_value=None)
        svc._extract_and_store_vault_entries = AsyncMock(return_value=0)

        fake_result = MagicMock()
        fake_result.summary_json = None     # ← LLM returned null
        fake_result.rendered_text = "some text"

        with patch(
            "app.services.deep_summary_service.DeepSummaryPipeline"
        ) as MockPipeline, patch(
            "app.services.deep_summary_service.SignatureEngine"
        ) as MockSig, patch(
            "app.services.deep_summary_service.VaultRetriever"
        ) as MockVR:
            MockPipeline.return_value.run = AsyncMock(return_value=fake_result)
            MockSig.return_value.get_active_profile = AsyncMock(return_value=None)
            MockVR.return_value.get_relevant_entries = AsyncMock(return_value=[])

            with pytest.raises(ValueError, match="empty summary_json"):
                await svc.generate_deep_summary(
                    patient_id=1, therapist_id=1, provider=MagicMock()
                )


# ── Cache gate: rendered_text required for cache hit ─────────────────────────

class TestDeepSummaryCacheGate:
    """generate_deep_summary cache hit requires BOTH json AND rendered_text."""

    @pytest.mark.asyncio
    async def test_no_cache_hit_when_rendered_text_missing(self):
        """If rendered_text is None in cache, should fall through to LLM even if json is set."""
        from app.services.deep_summary_service import DeepSummaryService

        summaries = _approved_summaries(2)
        fp = deep_summary_fingerprint(summaries)

        patient = _make_patient(
            ds_fp=fp,
            ds_fp_ver=FINGERPRINT_VERSION,
            ds_valid_until=cache_valid_until(),
            ds_json={"existing": "data"},
            ds_rendered=None,  # ← missing rendered_text
        )
        patient.id = 1

        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = patient

        svc = DeepSummaryService(db)
        svc._fetch_approved_summaries = MagicMock(return_value=summaries)
        svc._build_therapist_profile_dict = MagicMock(return_value={"modality": "cbt"})
        svc._get_active_plan_json = MagicMock(return_value=None)
        svc._extract_and_store_vault_entries = AsyncMock(return_value=0)
        svc._write_generation_log = MagicMock()

        fake_result = MagicMock()
        fake_result.summary_json = {"fresh": "data"}
        fake_result.rendered_text = "fresh rendered text"
        fake_result.model_used = "claude-3"
        fake_result.tokens_used = 200

        pipeline_run_called = []

        with patch(
            "app.services.deep_summary_service.DeepSummaryPipeline"
        ) as MockPipeline, patch(
            "app.services.deep_summary_service.SignatureEngine"
        ) as MockSig, patch(
            "app.services.deep_summary_service.VaultRetriever"
        ) as MockVR:
            async def track_run(*args, **kwargs):
                pipeline_run_called.append(True)
                return fake_result
            MockPipeline.return_value.run = track_run
            MockPipeline.return_value._extraction_results = []
            MockPipeline.return_value._synthesis_result = None
            MockPipeline.return_value._render_result = None
            MockSig.return_value.get_active_profile = AsyncMock(return_value=None)
            MockVR.return_value.get_relevant_entries = AsyncMock(return_value=[])

            result = await svc.generate_deep_summary(
                patient_id=1, therapist_id=1, provider=MagicMock()
            )

        # Pipeline MUST have been called (not a cache hit)
        assert len(pipeline_run_called) == 1
        assert result.rendered_text == "fresh rendered text"

    @pytest.mark.asyncio
    async def test_cache_hit_when_both_fields_present(self):
        """Full cache hit: json + rendered_text both set → NO LLM call."""
        from app.services.deep_summary_service import DeepSummaryService

        summaries = _approved_summaries(2)
        fp = deep_summary_fingerprint(summaries)

        patient = _make_patient(
            ds_fp=fp,
            ds_fp_ver=FINGERPRINT_VERSION,
            ds_valid_until=cache_valid_until(),
            ds_json={
                "arc_narrative": "A detailed treatment arc narrative with enough clinical content to pass validation",
                "treatment_phases": [{"phase": "initial assessment"}],
            },
            ds_rendered="cached rendered text with enough content to be valid",
            ds_sessions=2,
            ds_model="claude-3",
        )
        patient.id = 1

        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = patient

        svc = DeepSummaryService(db)
        svc._fetch_approved_summaries = MagicMock(return_value=summaries)

        pipeline_run_called = []

        with patch(
            "app.services.deep_summary_service.DeepSummaryPipeline"
        ) as MockPipeline:
            async def should_not_be_called(*args, **kwargs):
                pipeline_run_called.append(True)
                raise AssertionError("Pipeline should not be called on cache hit")
            MockPipeline.return_value.run = should_not_be_called

            result = await svc.generate_deep_summary(
                patient_id=1, therapist_id=1, provider=MagicMock()
            )

        assert not pipeline_run_called, "LLM pipeline was called on a valid cache hit"
        assert "arc_narrative" in result.summary_json
        assert result.rendered_text == "cached rendered text with enough content to be valid"


# ── update_plan cache check ───────────────────────────────────────────────────

class TestTreatmentPlanUpdateCache:
    """update_plan should use precompute cache just like create_plan."""

    def _make_db(self, patient, summaries, existing_plan):
        db = MagicMock()
        # First .filter().first() → patient; second chain → existing plan
        db.query.return_value.filter.return_value.first.side_effect = [patient, existing_plan]
        db.query.return_value.filter.return_value.order_by.return_value.first.return_value = existing_plan
        # _next_version uses .scalar() to get max version
        db.query.return_value.filter.return_value.scalar.return_value = existing_plan.version
        return db

    def _make_service(self, db, summaries):
        from app.services.treatment_plan_service import TreatmentPlanService
        svc = TreatmentPlanService(db)
        svc._fetch_approved_summaries = MagicMock(return_value=summaries)
        svc._build_therapist_profile_dict = MagicMock(return_value={"modality": "cbt"})
        return svc

    def _make_existing_plan(self, version=1):
        plan = MagicMock()
        plan.id = 99
        plan.version = version
        plan.plan_json = {"goals": ["old"]}
        plan.status = "active"
        return plan

    @pytest.mark.asyncio
    async def test_update_returns_cache_hit_when_valid(self):
        """update_plan must use precompute cache when fingerprint + TTL + both fields match."""
        summaries = _approved_summaries(3)
        fp = treatment_plan_fingerprint(summaries)
        patient = _make_patient(
            tp_fp=fp,
            tp_fp_ver=FINGERPRINT_VERSION,
            tp_valid_until=cache_valid_until(),
            tp_json={"primary_goals": [{"description": "cached goal"}], "presenting_problem": "anxiety"},
            tp_rendered="A comprehensive cached treatment plan with detailed clinical content for the patient.",
            tp_model="claude-3",
        )
        existing_plan = self._make_existing_plan(version=2)
        db = self._make_db(patient, summaries, existing_plan)
        svc = self._make_service(db, summaries)

        pipeline_called = []

        with patch(
            "app.services.treatment_plan_service.TreatmentPlanPipeline"
        ) as MockPipeline, patch(
            "app.services.treatment_plan_service.SignatureEngine"
        ) as MockSig:
            async def should_not_run(*args, **kwargs):
                pipeline_called.append(True)
                raise AssertionError("Pipeline should not be called on cache hit")
            MockPipeline.return_value.run = should_not_run
            MockSig.return_value.get_active_profile = AsyncMock(return_value=None)

            result = await svc.update_plan(
                patient_id=1, therapist_id=1, session_ids=None, provider=MagicMock()
            )

        assert not pipeline_called, "LLM pipeline was called on cache hit in update_plan"
        assert result.plan_json == {"primary_goals": [{"description": "cached goal"}], "presenting_problem": "anxiety"}
        assert result.rendered_text == "A comprehensive cached treatment plan with detailed clinical content for the patient."
        assert result.version == 3  # version incremented from existing
        assert result.parent_version_id == 99

    @pytest.mark.asyncio
    async def test_update_calls_llm_when_cache_missing_rendered_text(self):
        """update_plan must call LLM if rendered_text is None in cache."""
        summaries = _approved_summaries(2)
        fp = treatment_plan_fingerprint(summaries)
        patient = _make_patient(
            tp_fp=fp,
            tp_fp_ver=FINGERPRINT_VERSION,
            tp_valid_until=cache_valid_until(),
            tp_json={"goals": ["cached"]},
            tp_rendered=None,  # ← missing → must call LLM
        )
        existing_plan = self._make_existing_plan(version=1)
        db = self._make_db(patient, summaries, existing_plan)
        svc = self._make_service(db, summaries)

        fake_result = MagicMock()
        fake_result.plan_json = {"goals": ["fresh"]}
        fake_result.rendered_text = "fresh plan text"
        fake_result.model_used = "claude-3"
        fake_result.tokens_used = 80
        fake_result.version = 2

        with patch(
            "app.services.treatment_plan_service.TreatmentPlanPipeline"
        ) as MockPipeline, patch(
            "app.services.treatment_plan_service.SignatureEngine"
        ) as MockSig:
            MockPipeline.return_value.run = AsyncMock(return_value=fake_result)
            MockPipeline.return_value._last_extraction_result = None
            MockPipeline.return_value._last_render_result = None
            MockSig.return_value.get_active_profile = AsyncMock(return_value=None)

            result = await svc.update_plan(
                patient_id=1, therapist_id=1, session_ids=None, provider=MagicMock()
            )

        assert result.rendered_text == "fresh plan text"
        assert MockPipeline.return_value.run.called

    @pytest.mark.asyncio
    async def test_update_with_session_ids_always_calls_llm(self):
        """Selective plan update (session_ids set) must bypass cache."""
        summaries = _approved_summaries(2)
        fp = treatment_plan_fingerprint(summaries)
        patient = _make_patient(
            tp_fp=fp,
            tp_fp_ver=FINGERPRINT_VERSION,
            tp_valid_until=cache_valid_until(),
            tp_json={"goals": ["cached"]},
            tp_rendered="cached plan text",
        )
        existing_plan = self._make_existing_plan(version=1)
        db = self._make_db(patient, summaries, existing_plan)
        svc = self._make_service(db, summaries)

        fake_result = MagicMock()
        fake_result.plan_json = {"goals": ["selective"]}
        fake_result.rendered_text = "selective plan"
        fake_result.model_used = "claude-3"
        fake_result.tokens_used = 50
        fake_result.version = 2

        with patch(
            "app.services.treatment_plan_service.TreatmentPlanPipeline"
        ) as MockPipeline, patch(
            "app.services.treatment_plan_service.SignatureEngine"
        ) as MockSig:
            MockPipeline.return_value.run = AsyncMock(return_value=fake_result)
            MockPipeline.return_value._last_extraction_result = None
            MockPipeline.return_value._last_render_result = None
            MockSig.return_value.get_active_profile = AsyncMock(return_value=None)

            result = await svc.update_plan(
                patient_id=1, therapist_id=1, session_ids=[1, 2], provider=MagicMock()
            )

        # Cache must have been bypassed — LLM was called
        assert MockPipeline.return_value.run.called
        assert result.rendered_text == "selective plan"


# ── Prep fingerprint cache hit ────────────────────────────────────────────────

class TestPrepFingerprintCacheHit:
    """After the first LLM call warms the cache, subsequent calls with no data
    change must return from cache (fingerprint hit) without calling the LLM."""

    @pytest.mark.asyncio
    async def test_fingerprint_cache_hit_skips_llm(self):
        """If fingerprint matches + version matches, pipeline must NOT be called."""
        from datetime import datetime, timedelta
        from app.core.ai_cache import cache_valid_until
        from app.core.fingerprint import compute_fingerprint, FINGERPRINT_VERSION

        style_version = 1

        # The service computes the fingerprint from the ORM summary mock below.
        # summary_mock.approved_at = None → str(None) if None else None → None
        # Use the EXACT same payload the service builds during the fingerprint check.
        fp = compute_fingerprint({
            "mode": "concise",
            "summaries": [
                {
                    "summary_id": 1,
                    "approved_at": None,
                    "full_summary": "Summary one",
                }
            ],
            "style_version": style_version,
        })

        # Session cache is older than 10 min but fingerprint + 7-day TTL still valid
        old_generated_at = datetime.utcnow() - timedelta(minutes=20)

        session = MagicMock()
        session.id = 42
        session.patient_id = 7
        session.prep_json = {"sections": ["cached content"]}
        session.prep_rendered_text = "cached rendered prep"
        session.prep_mode = "concise"
        session.prep_generated_at = old_generated_at
        session.prep_input_fingerprint = fp
        session.prep_input_fingerprint_version = FINGERPRINT_VERSION
        session.prep_cache_valid_until = cache_valid_until()
        session.prep_completeness_score = 0.9

        # Inner summaries query (for fingerprint re-computation in service)
        summary_mock = MagicMock()
        summary_mock.approved_by_therapist = True
        summary_mock.id = 1
        summary_mock.approved_at = None  # → None in fingerprint payload (see fp above)
        summary_mock.full_summary = "Summary one"
        session_row = MagicMock()
        session_row.summary = summary_mock

        pipeline_called = []

        from app.ai.prep import PrepMode
        from app.services.session_service import SessionService

        agent = MagicMock()
        agent.profile = MagicMock()
        agent.profile.style_version = style_version

        db = MagicMock()

        def query_side_effect(model):
            q = MagicMock()
            # Session lookup (first filter().first())
            q.filter.return_value.first.return_value = session
            # Summaries for fingerprint (options().filter().order_by().all())
            q.options.return_value.filter.return_value.order_by.return_value.all.return_value = [session_row]
            return q

        db.query.side_effect = query_side_effect

        svc = SessionService(db)

        with patch("app.services.session_service.PrepPipeline") as MockPipeline:
            async def should_not_run(*a, **kw):
                pipeline_called.append(True)
                raise AssertionError("PrepPipeline should not be called on fingerprint cache hit")
            MockPipeline.return_value.run = should_not_run

            result = await svc.generate_prep_v2(
                session_id=42,
                therapist_id=1,
                mode=PrepMode.CONCISE,
                agent=agent,
            )

        assert not pipeline_called, "PrepPipeline was called despite fingerprint cache hit"
        assert result["rendered_text"] == "cached rendered prep"
