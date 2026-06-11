"""Unit tests for the Phase 10 summary task layer (no DB, no provider)."""

import pytest

from app.ai.models import FlowType
from app.ai.router import ModelRouter
from app.ai.summary_models import ReviseResult, SuggestResult
from app.ai.summary_tasks import (
    SummaryTaskType,
    TASK_REGISTRY,
    parse_strict,
    build_suggest_messages,
    build_revise_messages,
)


class TestRegistryCompleteness:
    def test_every_task_has_a_config(self):
        for task in SummaryTaskType:
            assert task in TASK_REGISTRY, f"{task} missing from TASK_REGISTRY"

    def test_non_ai_task_has_no_flow_type(self):
        cfg = TASK_REGISTRY[SummaryTaskType.SOURCE_SAVE]
        assert cfg.calls_ai is False
        assert cfg.flow_type is None

    def test_ai_tasks_have_routable_flow_types(self):
        router = ModelRouter()
        for task, cfg in TASK_REGISTRY.items():
            if cfg.calls_ai:
                assert cfg.flow_type is not None
                # resolve() must not raise and must return a non-empty model id
                model_id, reason = router.resolve(cfg.flow_type)
                assert model_id
                assert reason

    def test_suggest_does_not_persist(self):
        assert TASK_REGISTRY[SummaryTaskType.SOURCE_SUMMARY_SUGGEST].persists_summary is False

    def test_new_flow_types_registered_in_routing_table(self):
        assert FlowType.SUMMARY_SUGGEST in ModelRouter.ROUTING_TABLE
        assert FlowType.SUMMARY_REVISE in ModelRouter.ROUTING_TABLE


class TestParseStrict:
    def test_valid_suggest_payload(self):
        raw = '{"suggestions": [{"category": "missing", "text": "Add mood", "severity": "info"}], "overall_note": null}'
        result = parse_strict(raw, SuggestResult)
        assert isinstance(result, SuggestResult)
        assert len(result.suggestions) == 1
        assert result.suggestions[0].category == "missing"

    def test_valid_payload_with_code_fences(self):
        raw = '```json\n{"revised_summary": "text", "change_note": null, "confidence": 0.9}\n```'
        result = parse_strict(raw, ReviseResult)
        assert isinstance(result, ReviseResult)
        assert result.revised_summary == "text"

    def test_extra_field_rejected(self):
        # A suggest response that tries to smuggle in a rewrite must be rejected.
        raw = '{"suggestions": [], "overall_note": null, "rewritten_summary": "SNEAKY REWRITE"}'
        result = parse_strict(raw, SuggestResult)
        assert result is None

    def test_non_json_returns_none(self):
        assert parse_strict("this is not json at all", SuggestResult) is None

    def test_non_object_returns_none(self):
        assert parse_strict("[1, 2, 3]", SuggestResult) is None

    def test_wrong_type_rejected(self):
        # suggestions must be a list; a string should fail validation
        raw = '{"suggestions": "not a list", "overall_note": null}'
        assert parse_strict(raw, SuggestResult) is None


class TestPromptBuilders:
    def test_suggest_prompt_is_advisory_only(self):
        system, user = build_suggest_messages("patient reported anxiety", modality_pack=None)
        assert "MUST NOT rewrite" in system
        assert "patient reported anxiety" in user

    def test_suggest_prompt_includes_draft_when_present(self):
        system, user = build_suggest_messages(
            "source notes", modality_pack=None, existing_draft="the current draft",
        )
        assert "the current draft" in user
        assert "do NOT rewrite" in user.lower() or "do not rewrite" in user.lower()

    def test_revise_prompt_is_single_shot(self):
        system, user = build_revise_messages("current draft", "make it shorter", modality_pack=None)
        assert "SINGLE-SHOT" in system
        assert "make it shorter" in user
        assert "current draft" in user
