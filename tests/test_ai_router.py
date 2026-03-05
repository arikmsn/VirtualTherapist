"""Tests for ModelRouter — routing conditions and escalation rules."""

import pytest
from unittest.mock import patch

from app.ai.models import FlowType
from app.ai.router import ModelRouter


@pytest.fixture
def router():
    return ModelRouter()


# ── Default tier routing ───────────────────────────────────────────────────────

class TestDefaultTierRouting:
    def test_extraction_routes_to_fast(self, router):
        model, reason = router.resolve(FlowType.EXTRACTION)
        assert "fast" in reason

    def test_completeness_check_routes_to_fast(self, router):
        model, reason = router.resolve(FlowType.COMPLETENESS_CHECK)
        assert "fast" in reason

    def test_session_summary_routes_to_standard(self, router):
        model, reason = router.resolve(FlowType.SESSION_SUMMARY)
        assert "standard" in reason

    def test_chat_routes_to_standard(self, router):
        model, reason = router.resolve(FlowType.CHAT)
        assert "standard" in reason

    def test_session_prep_routes_to_standard(self, router):
        model, reason = router.resolve(FlowType.SESSION_PREP)
        assert "standard" in reason

    def test_patient_insight_routes_to_standard(self, router):
        model, reason = router.resolve(FlowType.PATIENT_INSIGHT)
        assert "standard" in reason

    def test_deep_summary_routes_to_deep(self, router):
        model, reason = router.resolve(FlowType.DEEP_SUMMARY)
        assert "deep" in reason

    def test_treatment_plan_routes_to_deep(self, router):
        model, reason = router.resolve(FlowType.TREATMENT_PLAN)
        assert "deep" in reason

    def test_twin_profile_routes_to_deep(self, router):
        model, reason = router.resolve(FlowType.TWIN_PROFILE)
        assert "deep" in reason


# ── Model IDs come from settings ──────────────────────────────────────────────

class TestModelIdFromSettings:
    def test_model_ids_are_strings(self, router):
        for flow in FlowType:
            model, _ = router.resolve(flow)
            assert isinstance(model, str) and len(model) > 0

    def test_fast_model_from_settings(self, router):
        model, _ = router.resolve(FlowType.EXTRACTION)
        from app.core.config import settings
        assert model == settings.AI_FAST_MODEL

    def test_standard_model_from_settings(self, router):
        model, _ = router.resolve(FlowType.SESSION_SUMMARY)
        from app.core.config import settings
        assert model == settings.AI_STANDARD_MODEL

    def test_deep_model_from_settings(self, router):
        model, _ = router.resolve(FlowType.TREATMENT_PLAN)
        from app.core.config import settings
        assert model == settings.AI_DEEP_MODEL


# ── Escalation: model_override ────────────────────────────────────────────────

class TestOverrideEscalation:
    def test_override_bypasses_routing(self, router):
        custom = "custom-model-id-123"
        model, reason = router.resolve(FlowType.CHAT, model_override=custom)
        assert model == custom
        assert reason == "override"

    def test_override_on_deep_flow_still_uses_override(self, router):
        custom = "tiny-model"
        model, reason = router.resolve(FlowType.TWIN_PROFILE, model_override=custom)
        assert model == custom


# ── Escalation: deep_mode flag ────────────────────────────────────────────────

class TestDeepModeEscalation:
    def test_deep_mode_escalates_standard_to_deep(self, router):
        model_no_deep, _ = router.resolve(FlowType.SESSION_SUMMARY)
        model_deep, reason = router.resolve(FlowType.SESSION_SUMMARY, deep_mode=True)

        from app.core.config import settings
        assert model_no_deep == settings.AI_STANDARD_MODEL
        assert model_deep == settings.AI_DEEP_MODEL
        assert "deep_mode" in reason

    def test_deep_mode_on_already_deep_flow_unchanged(self, router):
        model, reason = router.resolve(FlowType.TREATMENT_PLAN, deep_mode=True)
        from app.core.config import settings
        assert model == settings.AI_DEEP_MODEL
        # deep_mode not in reason because tier was already deep
        assert "deep_mode" not in reason

    def test_deep_mode_on_fast_flow_unchanged(self, router):
        # fast flows are never escalated by deep_mode (only standard tier is)
        model, reason = router.resolve(FlowType.EXTRACTION, deep_mode=True)
        from app.core.config import settings
        assert model == settings.AI_FAST_MODEL
        assert "deep_mode" not in reason


# ── Escalation: long history ──────────────────────────────────────────────────

class TestLongHistoryEscalation:
    THRESHOLD = ModelRouter.LONG_HISTORY_THRESHOLD

    def test_below_threshold_stays_standard(self, router):
        model, reason = router.resolve(
            FlowType.SESSION_SUMMARY, session_count=self.THRESHOLD
        )
        from app.core.config import settings
        assert model == settings.AI_STANDARD_MODEL
        assert "long_history" not in reason

    def test_above_threshold_escalates_to_deep(self, router):
        model, reason = router.resolve(
            FlowType.SESSION_SUMMARY, session_count=self.THRESHOLD + 1
        )
        from app.core.config import settings
        assert model == settings.AI_DEEP_MODEL
        assert "long_history" in reason

    def test_long_history_does_not_escalate_non_escalatable_flow(self, router):
        # CHAT is not in _HISTORY_ESCALATABLE so should stay standard
        model, reason = router.resolve(FlowType.CHAT, session_count=self.THRESHOLD + 5)
        from app.core.config import settings
        assert model == settings.AI_STANDARD_MODEL
        assert "long_history" not in reason

    def test_long_history_escalates_session_prep(self, router):
        model, reason = router.resolve(
            FlowType.SESSION_PREP, session_count=self.THRESHOLD + 1
        )
        from app.core.config import settings
        assert model == settings.AI_DEEP_MODEL

    def test_long_history_escalates_patient_insight(self, router):
        model, reason = router.resolve(
            FlowType.PATIENT_INSIGHT, session_count=self.THRESHOLD + 1
        )
        from app.core.config import settings
        assert model == settings.AI_DEEP_MODEL


# ── Escalation: low confidence ────────────────────────────────────────────────

class TestLowConfidenceEscalation:
    THRESHOLD = ModelRouter.LOW_CONFIDENCE_THRESHOLD

    def test_above_threshold_stays_standard(self, router):
        model, reason = router.resolve(
            FlowType.SESSION_SUMMARY, prior_confidence=self.THRESHOLD
        )
        from app.core.config import settings
        assert model == settings.AI_STANDARD_MODEL
        assert "low_confidence" not in reason

    def test_below_threshold_escalates(self, router):
        model, reason = router.resolve(
            FlowType.SESSION_SUMMARY, prior_confidence=self.THRESHOLD - 0.01
        )
        from app.core.config import settings
        assert model == settings.AI_DEEP_MODEL
        assert "low_confidence" in reason

    def test_zero_confidence_escalates(self, router):
        model, reason = router.resolve(FlowType.SESSION_PREP, prior_confidence=0.0)
        from app.core.config import settings
        assert model == settings.AI_DEEP_MODEL

    def test_none_confidence_does_not_escalate(self, router):
        model, reason = router.resolve(FlowType.SESSION_SUMMARY, prior_confidence=None)
        from app.core.config import settings
        assert model == settings.AI_STANDARD_MODEL


# ── Escalation priority: override wins over everything ────────────────────────

class TestEscalationPriority:
    def test_override_beats_deep_mode(self, router):
        custom = "override-model"
        model, reason = router.resolve(
            FlowType.SESSION_SUMMARY,
            model_override=custom,
            deep_mode=True,
        )
        assert model == custom
        assert reason == "override"

    def test_override_beats_long_history(self, router):
        custom = "override-model"
        model, reason = router.resolve(
            FlowType.SESSION_SUMMARY,
            model_override=custom,
            session_count=999,
        )
        assert model == custom
        assert reason == "override"


# ── Route reason format ───────────────────────────────────────────────────────

class TestRouteReasonFormat:
    def test_reason_includes_flow_type(self, router):
        _, reason = router.resolve(FlowType.SESSION_SUMMARY)
        assert "flow:session_summary" in reason

    def test_reason_includes_tier(self, router):
        _, reason = router.resolve(FlowType.SESSION_SUMMARY)
        assert "tier:standard" in reason

    def test_reason_includes_deep_tier_for_deep_flows(self, router):
        _, reason = router.resolve(FlowType.TREATMENT_PLAN)
        assert "tier:deep" in reason
