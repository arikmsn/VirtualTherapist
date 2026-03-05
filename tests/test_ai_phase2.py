"""Tests for Phase 2 — modality pack resolution, prompt assembly, and completeness checker."""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.ai.completeness import CompletenessChecker, CompletenessResult
from app.ai.modality import assemble_system_prompt, HEBREW_QUALITY_RULE
from app.ai.models import FlowType
from app.ai.provider import GenerationResult


# ── CompletenessResult dataclass ──────────────────────────────────────────────

class TestCompletenessResult:
    def test_full_returns_score_one(self):
        r = CompletenessResult.full()
        assert r.score == 1.0
        assert r.required_missing == []
        assert r.recommended_missing == []

    def test_error_returns_negative_score(self):
        r = CompletenessResult.error()
        assert r.score == -1.0
        assert r.modality_notes == "checker_error"

    def test_to_dict(self):
        r = CompletenessResult(
            score=0.8,
            required_missing=["risk_assessment"],
            recommended_missing=["homework_assigned"],
            modality_notes="risk missing",
        )
        d = r.to_dict()
        assert d["score"] == 0.8
        assert d["required_missing"] == ["risk_assessment"]
        assert d["recommended_missing"] == ["homework_assigned"]
        assert d["modality_notes"] == "risk missing"


# ── assemble_system_prompt ─────────────────────────────────────────────────────

class TestAssembleSystemPrompt:
    def test_no_modality_includes_quality_rule(self):
        result = assemble_system_prompt("base prompt here", modality_pack=None)
        assert HEBREW_QUALITY_RULE.strip() in result
        assert "base prompt here" in result

    def test_with_modality_pack_includes_module(self):
        mock_pack = MagicMock()
        mock_pack.prompt_module = "## CBT FRAMING\nFocus on thoughts and behaviors."
        mock_pack.label = "CBT"

        result = assemble_system_prompt("base prompt", modality_pack=mock_pack)
        assert "CBT FRAMING" in result
        assert HEBREW_QUALITY_RULE.strip() in result
        assert "base prompt" in result

    def test_layer_order_modality_before_quality_before_base(self):
        mock_pack = MagicMock()
        mock_pack.prompt_module = "MODALITY_BLOCK"
        mock_pack.label = "Test"

        result = assemble_system_prompt("BASE_BLOCK", modality_pack=mock_pack)
        modality_pos = result.index("MODALITY_BLOCK")
        quality_pos = result.index(HEBREW_QUALITY_RULE.strip()[:20])
        base_pos = result.index("BASE_BLOCK")

        assert modality_pos < quality_pos < base_pos

    def test_modality_pack_with_empty_prompt_module(self):
        mock_pack = MagicMock()
        mock_pack.prompt_module = ""
        mock_pack.label = "Test"

        result = assemble_system_prompt("base", modality_pack=mock_pack)
        assert "base" in result
        assert HEBREW_QUALITY_RULE.strip() in result

    def test_modality_pack_with_none_prompt_module(self):
        mock_pack = MagicMock()
        mock_pack.prompt_module = None
        mock_pack.label = "Test"

        result = assemble_system_prompt("base", modality_pack=mock_pack)
        assert "base" in result
        assert HEBREW_QUALITY_RULE.strip() in result


# ── CompletenessChecker ────────────────────────────────────────────────────────

def _make_provider_with_json_response(json_payload: dict) -> MagicMock:
    """Helper: create a mock AIProvider that returns the given JSON payload as content."""
    mock_provider = MagicMock()
    mock_result = MagicMock(spec=GenerationResult)
    mock_result.content = json.dumps(json_payload)
    mock_result.model_used = "claude-haiku-test"
    mock_result.route_reason = "flow:completeness_check,tier:fast"
    mock_result.prompt_tokens = 100
    mock_result.completion_tokens = 30
    mock_result.generation_ms = 150
    mock_provider.generate = AsyncMock(return_value=mock_result)
    return mock_provider


def _make_modality_pack(
    name="cbt",
    label="CBT",
    required=None,
    recommended=None,
) -> MagicMock:
    pack = MagicMock()
    pack.name = name
    pack.label = label
    pack.required_summary_fields = required or []
    pack.recommended_summary_fields = recommended or []
    return pack


class TestCompletenessCheckerNoModality:
    @pytest.mark.asyncio
    async def test_returns_full_when_no_modality_pack(self):
        provider = MagicMock()
        checker = CompletenessChecker(provider)
        result = await checker.check("some summary text", modality_pack=None)
        assert result.score == 1.0
        provider.generate.assert_not_called() if hasattr(provider, "generate") else None

    @pytest.mark.asyncio
    async def test_returns_full_when_pack_has_no_fields(self):
        provider = MagicMock()
        provider.generate = AsyncMock()
        checker = CompletenessChecker(provider)
        pack = _make_modality_pack(required=[], recommended=[])
        result = await checker.check("some summary text", modality_pack=pack)
        assert result.score == 1.0
        provider.generate.assert_not_called()


class TestCompletenessCheckerWithModality:
    @pytest.mark.asyncio
    async def test_all_fields_present_returns_high_score(self):
        provider = _make_provider_with_json_response({
            "score": 1.0,
            "required_missing": [],
            "recommended_missing": [],
            "modality_notes": "",
        })
        checker = CompletenessChecker(provider)
        pack = _make_modality_pack(
            required=["full_summary", "risk_assessment"],
            recommended=["homework_assigned"],
        )
        result = await checker.check("Complete session summary with all fields.", pack)
        assert result.score == 1.0
        assert result.required_missing == []
        assert result.recommended_missing == []
        assert result.modality_notes == ""

    @pytest.mark.asyncio
    async def test_missing_required_cbt_homework(self):
        provider = _make_provider_with_json_response({
            "score": 0.6,
            "required_missing": ["homework_assigned"],
            "recommended_missing": [],
            "modality_notes": "CBT requires homework; section is empty",
        })
        checker = CompletenessChecker(provider)
        pack = _make_modality_pack(
            name="cbt",
            required=["full_summary", "homework_assigned"],
        )
        result = await checker.check("Summary without homework.", pack)
        assert result.score == 0.6
        assert "homework_assigned" in result.required_missing
        assert "CBT" in result.modality_notes or "homework" in result.modality_notes.lower()

    @pytest.mark.asyncio
    async def test_missing_required_clinical_risk(self):
        """Clinical psychologist pack: risk_assessment is required."""
        provider = _make_provider_with_json_response({
            "score": 0.5,
            "required_missing": ["risk_assessment"],
            "recommended_missing": [],
            "modality_notes": "risk_assessment is required but missing",
        })
        checker = CompletenessChecker(provider)
        pack = _make_modality_pack(
            name="clinical_psychologist",
            required=["full_summary", "risk_assessment"],
        )
        result = await checker.check("Summary without risk assessment.", pack)
        assert "risk_assessment" in result.required_missing

    @pytest.mark.asyncio
    async def test_checker_uses_fast_model_flow_type(self):
        """CompletenessChecker must use FlowType.COMPLETENESS_CHECK."""
        provider = _make_provider_with_json_response({
            "score": 1.0, "required_missing": [], "recommended_missing": [], "modality_notes": "",
        })
        checker = CompletenessChecker(provider)
        pack = _make_modality_pack(required=["full_summary"])

        await checker.check("summary text", pack)

        call_kwargs = provider.generate.call_args.kwargs
        assert call_kwargs.get("flow_type") == FlowType.COMPLETENESS_CHECK

    @pytest.mark.asyncio
    async def test_last_result_stored_after_check(self):
        provider = _make_provider_with_json_response({
            "score": 0.9, "required_missing": [], "recommended_missing": [], "modality_notes": "",
        })
        checker = CompletenessChecker(provider)
        pack = _make_modality_pack(required=["full_summary"])

        await checker.check("summary text", pack)

        assert checker._last_result is not None
        assert checker._last_result.model_used == "claude-haiku-test"

    @pytest.mark.asyncio
    async def test_returns_error_result_on_json_parse_failure(self):
        mock_provider = MagicMock()
        bad_result = MagicMock()
        bad_result.content = "not valid json at all {{{"
        mock_provider.generate = AsyncMock(return_value=bad_result)

        checker = CompletenessChecker(mock_provider)
        pack = _make_modality_pack(required=["full_summary"])
        result = await checker.check("summary", pack)

        assert result.score == -1.0
        assert result.modality_notes == "checker_error"

    @pytest.mark.asyncio
    async def test_returns_error_result_on_provider_exception(self):
        mock_provider = MagicMock()
        mock_provider.generate = AsyncMock(side_effect=RuntimeError("network error"))

        checker = CompletenessChecker(mock_provider)
        pack = _make_modality_pack(required=["full_summary"])
        result = await checker.check("summary", pack)

        assert result.score == -1.0
        assert result.modality_notes == "checker_error"

    @pytest.mark.asyncio
    async def test_strips_markdown_code_fences(self):
        """Model sometimes wraps JSON in ```json ... ```"""
        mock_provider = MagicMock()
        mock_result = MagicMock()
        mock_result.content = '```json\n{"score": 0.95, "required_missing": [], "recommended_missing": [], "modality_notes": ""}\n```'
        mock_result.model_used = "haiku"
        mock_result.route_reason = ""
        mock_result.prompt_tokens = 50
        mock_result.completion_tokens = 20
        mock_result.generation_ms = 100
        mock_provider.generate = AsyncMock(return_value=mock_result)

        checker = CompletenessChecker(mock_provider)
        pack = _make_modality_pack(required=["full_summary"])
        result = await checker.check("summary text", pack)

        assert result.score == 0.95


# ── resolve_modality_pack ─────────────────────────────────────────────────────

class TestResolveModalityPack:
    def test_returns_explicit_therapist_pack(self):
        from app.ai.modality import resolve_modality_pack
        from app.models.modality import ModalityPack
        from app.models.therapist import TherapistProfile

        mock_pack = MagicMock(spec=ModalityPack)
        mock_pack.id = 2
        mock_pack.is_active = True

        mock_profile = MagicMock(spec=TherapistProfile)
        mock_profile.therapist_id = 1
        mock_profile.modality_pack_id = 2

        mock_db = MagicMock()

        # Query chain: TherapistProfile → profile, ModalityPack → pack
        def query_side_effect(model):
            q = MagicMock()
            if model is TherapistProfile:
                q.filter.return_value.first.return_value = mock_profile
            elif model is ModalityPack:
                inner = MagicMock()
                inner.filter.return_value.first.return_value = mock_pack
                q.filter.return_value = inner.filter.return_value
            return q

        mock_db.query.side_effect = query_side_effect

        result = resolve_modality_pack(mock_db, therapist_id=1)
        assert result is mock_pack

    def test_falls_back_to_generic_integrative_when_no_explicit_pack(self):
        from app.ai.modality import resolve_modality_pack
        from app.models.modality import ModalityPack
        from app.models.therapist import TherapistProfile

        mock_generic = MagicMock(spec=ModalityPack)
        mock_generic.name = "generic_integrative"

        mock_profile = MagicMock(spec=TherapistProfile)
        mock_profile.modality_pack_id = None

        mock_db = MagicMock()

        def query_side_effect(model):
            q = MagicMock()
            if model is TherapistProfile:
                q.filter.return_value.first.return_value = mock_profile
            elif model is ModalityPack:
                q.filter.return_value.first.return_value = mock_generic
            return q

        mock_db.query.side_effect = query_side_effect

        result = resolve_modality_pack(mock_db, therapist_id=1)
        assert result is mock_generic
