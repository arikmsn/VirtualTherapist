"""
Tests for Phase 3 — Session Summary 2.0 pipeline.

Coverage:
- SummaryInput dataclass
- compute_edit_distance
- _parse_clinical_json (fallback and happy path)
- _build_extraction_system_prompt / _build_render_prompt
- SummaryPipeline (extraction + render calls, result storage)
- _assemble_summary_input: last_approved_summary from approved rows ONLY
- Full pipeline produces prose (not JSON)
- edit_distance stored on approval
"""

import json
import pytest
from dataclasses import fields
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

from app.ai.models import FlowType
from app.ai.summary_pipeline import (
    CLINICAL_JSON_SCHEMA,
    SummaryInput,
    SummaryPipeline,
    _build_extraction_system_prompt,
    _build_render_prompt,
    _parse_clinical_json,
    compute_edit_distance,
)


# ── SummaryInput ──────────────────────────────────────────────────────────────

class TestSummaryInput:
    def test_required_fields_present(self):
        field_names = {f.name for f in fields(SummaryInput)}
        required = {
            "raw_content", "client_name", "session_number", "session_date",
            "last_approved_summary", "open_tasks", "modality_pack",
            "therapist_signature", "flow_type",
        }
        assert required.issubset(field_names)

    def test_instantiation_with_defaults(self):
        inp = SummaryInput(
            raw_content="Notes from session",
            client_name="דוד",
            session_number=3,
            session_date=date(2026, 3, 6),
            last_approved_summary=None,
            open_tasks=[],
            modality_pack=None,
            therapist_signature=None,
        )
        assert inp.flow_type == FlowType.SESSION_SUMMARY
        assert inp.session_number == 3

    def test_with_open_tasks_and_prior_summary(self):
        inp = SummaryInput(
            raw_content="Session notes",
            client_name="שרה",
            session_number=7,
            session_date=date(2026, 3, 6),
            last_approved_summary="Previous approved summary text.",
            open_tasks=["practice breathing exercises", "keep a thought journal"],
            modality_pack=None,
            therapist_signature=None,
        )
        assert len(inp.open_tasks) == 2
        assert inp.last_approved_summary == "Previous approved summary text."


# ── compute_edit_distance ─────────────────────────────────────────────────────

class TestComputeEditDistance:
    def test_identical_strings_zero_distance(self):
        assert compute_edit_distance("hello", "hello") == 0

    def test_empty_strings_zero_distance(self):
        assert compute_edit_distance("", "") == 0

    def test_one_empty_returns_length_of_other(self):
        assert compute_edit_distance("", "hello") == 5
        assert compute_edit_distance("hello", "") == 5

    def test_completely_different_strings(self):
        dist = compute_edit_distance("abc", "xyz")
        assert dist > 0

    def test_small_edit_returns_small_distance(self):
        # One character changed
        dist = compute_edit_distance("hello world", "hello World")
        assert 0 < dist <= 5

    def test_large_rewrite_large_distance(self):
        original = "דוד עסק בדיסוציאציה ובחרדה מופנמת"
        rewrite = "המטופלת דיווחה על שיפור בניהול מצבי לחץ ועל ירידה בתדירות מחשבות חרדה"
        dist = compute_edit_distance(original, rewrite)
        assert dist > 20

    def test_minor_whitespace_change_low_distance(self):
        dist = compute_edit_distance("  hello  ", " hello ")
        assert dist < 5

    def test_hebrew_text(self):
        a = "המטופל דיווח על שיפור"
        b = "המטופל דיווח על שיפור ניכר"
        dist = compute_edit_distance(a, b)
        assert 0 < dist <= 15


# ── _parse_clinical_json ──────────────────────────────────────────────────────

class TestParseClinicalJson:
    def test_valid_json_returns_dict(self):
        data = {"session_focus": "חרדה", "key_themes": ["חרדה", "בית"], "confidence": 0.9}
        result = _parse_clinical_json(json.dumps(data))
        assert result["session_focus"] == "חרדה"
        assert result["confidence"] == 0.9

    def test_json_with_markdown_fences_stripped(self):
        raw = '```json\n{"session_focus": "test", "confidence": 0.8}\n```'
        result = _parse_clinical_json(raw)
        assert result["session_focus"] == "test"

    def test_invalid_json_returns_empty_scaffold(self):
        result = _parse_clinical_json("not valid json {{{{")
        assert isinstance(result, dict)
        assert "session_focus" in result
        assert result["confidence"] == 0.0
        assert result["key_themes"] == []

    def test_empty_string_returns_scaffold(self):
        result = _parse_clinical_json("")
        assert isinstance(result, dict)
        assert result["risk_assessment"]["risk_present"] is False

    def test_non_dict_json_returns_scaffold(self):
        result = _parse_clinical_json('["list", "not", "dict"]')
        assert isinstance(result, dict)
        assert "session_focus" in result


# ── Prompt builders ───────────────────────────────────────────────────────────

class TestExtractionSystemPrompt:
    def test_no_modality_has_json_instruction(self):
        prompt = _build_extraction_system_prompt(modality_pack=None)
        assert "JSON" in prompt
        assert "extraction" in prompt.lower()

    def test_with_modality_includes_prompt_module(self):
        mock_pack = MagicMock()
        mock_pack.prompt_module = "## CBT Framework\nFocus on cognitive model."
        prompt = _build_extraction_system_prompt(modality_pack=mock_pack)
        assert "CBT Framework" in prompt

    def test_with_modality_having_no_prompt_module(self):
        mock_pack = MagicMock()
        mock_pack.prompt_module = None
        prompt = _build_extraction_system_prompt(modality_pack=mock_pack)
        assert "JSON" in prompt


class TestRenderPrompt:
    def test_includes_clinical_json(self):
        inp = SummaryInput(
            raw_content="notes",
            client_name="דוד",
            session_number=1,
            session_date=date(2026, 1, 1),
            last_approved_summary=None,
            open_tasks=[],
            modality_pack=None,
            therapist_signature=None,
        )
        clinical_json = {"session_focus": "חרדה", "confidence": 0.9}
        prompt = _build_render_prompt(inp, clinical_json)
        assert "חרדה" in prompt
        # confidence is intentionally stripped from render prompt to prevent
        # the LLM from embedding disclaimer/confidence text in the summary
        assert "0.9" not in prompt

    def test_no_missing_elements_instruction(self):
        """Render prompt should NOT instruct the LLM to flag missing elements."""
        inp = SummaryInput(
            raw_content="notes",
            client_name="שרה",
            session_number=2,
            session_date=date(2026, 1, 1),
            last_approved_summary=None,
            open_tasks=[],
            modality_pack=None,
            therapist_signature=None,
        )
        prompt = _build_render_prompt(inp, {})
        assert "⚠️ חסר:" not in prompt


# ── SummaryPipeline ───────────────────────────────────────────────────────────

def _make_summary_input(
    raw_content="פגישה 3 — עבדנו על מחשבות אוטומטיות וחרדת ביצוע",
    client_name="דוד",
    last_approved=None,
) -> SummaryInput:
    return SummaryInput(
        raw_content=raw_content,
        client_name=client_name,
        session_number=3,
        session_date=date(2026, 3, 6),
        last_approved_summary=last_approved,
        open_tasks=["לנהל יומן מחשבות"],
        modality_pack=None,
        therapist_signature=None,
    )


def _make_agent_with_two_responses(extraction_json: dict, render_text: str) -> MagicMock:
    """Build a mock agent whose provider.generate() returns different values per call."""
    provider = MagicMock()
    call_count = {"n": 0}

    async def generate_side_effect(**kwargs):
        result = MagicMock()
        result.model_used = "claude-sonnet-test"
        result.route_reason = "flow:session_summary,tier:standard"
        result.prompt_tokens = 200
        result.completion_tokens = 100
        result.generation_ms = 500

        if call_count["n"] == 0:
            result.content = json.dumps(extraction_json, ensure_ascii=False)
        else:
            result.content = render_text
        call_count["n"] += 1
        return result

    provider.generate = AsyncMock(side_effect=generate_side_effect)

    agent = MagicMock()
    agent.provider = provider
    agent.system_prompt = "Mock system prompt"
    agent._last_result = None
    return agent


class TestSummaryPipelineExtraction:
    @pytest.mark.asyncio
    async def test_extraction_call_uses_session_summary_flow(self):
        clinical_data = {
            "session_focus": "חרדה", "key_themes": ["חרדה"],
            "interventions_used": [], "client_response": "",
            "homework_reviewed": {"was_reviewed": False, "completed": None, "barriers": None},
            "automatic_thoughts": [], "cognitive_distortions": [],
            "new_homework": None, "mood_observed": None,
            "risk_assessment": {"risk_present": False, "notes": None},
            "next_session_focus": None, "longitudinal_note": None, "confidence": 0.85,
        }
        agent = _make_agent_with_two_responses(clinical_data, "Summary prose in Hebrew")
        pipeline = SummaryPipeline(agent)

        inp = _make_summary_input()
        await pipeline.run(inp)

        # Both calls should use FlowType.SESSION_SUMMARY
        calls = agent.provider.generate.call_args_list
        assert len(calls) == 2
        for call in calls:
            assert call.kwargs["flow_type"] == FlowType.SESSION_SUMMARY

    @pytest.mark.asyncio
    async def test_extraction_call_1_uses_json_system_prompt(self):
        clinical_data = {"session_focus": "test", "confidence": 0.7, "key_themes": []}
        agent = _make_agent_with_two_responses(clinical_data, "Hebrew prose")
        pipeline = SummaryPipeline(agent)

        await pipeline.run(_make_summary_input())

        # First call (extraction) should NOT use agent.system_prompt
        first_call_messages = agent.provider.generate.call_args_list[0].kwargs["messages"]
        system_msgs = [m for m in first_call_messages if m["role"] == "system"]
        assert system_msgs[0]["content"] != agent.system_prompt

    @pytest.mark.asyncio
    async def test_render_call_2_uses_agent_system_prompt(self):
        clinical_data = {"session_focus": "test", "confidence": 0.7, "key_themes": []}
        agent = _make_agent_with_two_responses(clinical_data, "Hebrew prose")
        pipeline = SummaryPipeline(agent)

        await pipeline.run(_make_summary_input())

        # Second call (render) should use agent.system_prompt
        second_call_messages = agent.provider.generate.call_args_list[1].kwargs["messages"]
        system_msgs = [m for m in second_call_messages if m["role"] == "system"]
        assert system_msgs[0]["content"] == "Mock system prompt"


class TestSummaryPipelineResults:
    @pytest.mark.asyncio
    async def test_run_returns_dict_and_string(self):
        clinical_data = {"session_focus": "test", "key_themes": [], "confidence": 0.8}
        render_text = "זוהי סיכום הפגישה בעברית טבעית ומקצועית."
        agent = _make_agent_with_two_responses(clinical_data, render_text)
        pipeline = SummaryPipeline(agent)

        result_json, result_text = await pipeline.run(_make_summary_input())

        assert isinstance(result_json, dict)
        assert isinstance(result_text, str)
        assert result_text == render_text

    @pytest.mark.asyncio
    async def test_rendered_text_is_prose_not_json(self):
        clinical_data = {"session_focus": "בחרדה", "key_themes": [], "confidence": 0.9}
        render_text = "המטופל עסק בחרדה ושיפר את הכישורים שלו בניהול מחשבות."
        agent = _make_agent_with_two_responses(clinical_data, render_text)
        pipeline = SummaryPipeline(agent)

        _, rendered = await pipeline.run(_make_summary_input())

        # Should be natural prose, not parseable JSON
        assert not rendered.startswith("{")
        try:
            json.loads(rendered)
            assert False, "Rendered text should not be valid JSON"
        except json.JSONDecodeError:
            pass  # expected

    @pytest.mark.asyncio
    async def test_last_extraction_result_stored(self):
        clinical_data = {"session_focus": "test", "confidence": 0.7}
        agent = _make_agent_with_two_responses(clinical_data, "prose")
        pipeline = SummaryPipeline(agent)

        await pipeline.run(_make_summary_input())

        assert pipeline._last_extraction_result is not None
        assert pipeline._last_extraction_result.model_used == "claude-sonnet-test"

    @pytest.mark.asyncio
    async def test_last_render_result_stored(self):
        clinical_data = {"session_focus": "test", "confidence": 0.7}
        agent = _make_agent_with_two_responses(clinical_data, "prose text")
        pipeline = SummaryPipeline(agent)

        await pipeline.run(_make_summary_input())

        assert pipeline._last_render_result is not None
        assert pipeline._last_render_result.content == "prose text"

    @pytest.mark.asyncio
    async def test_agent_last_result_set_to_render_result(self):
        """agent._last_result should hold the render result after run() — for telemetry."""
        clinical_data = {"session_focus": "test", "confidence": 0.9}
        agent = _make_agent_with_two_responses(clinical_data, "rendered prose")
        pipeline = SummaryPipeline(agent)

        await pipeline.run(_make_summary_input())

        assert agent._last_result is not None
        assert agent._last_result.content == "rendered prose"

    @pytest.mark.asyncio
    async def test_invalid_extraction_json_falls_back_to_scaffold(self):
        """If the model returns non-JSON in Call 1, pipeline uses an empty scaffold."""
        provider = MagicMock()
        call_count = {"n": 0}

        async def generate(**kwargs):
            result = MagicMock()
            result.model_used = "test"
            result.route_reason = ""
            result.prompt_tokens = 50
            result.completion_tokens = 20
            result.generation_ms = 100
            if call_count["n"] == 0:
                result.content = "THIS IS NOT JSON AT ALL"
            else:
                result.content = "Rendered Hebrew prose"
            call_count["n"] += 1
            return result

        provider.generate = AsyncMock(side_effect=generate)
        agent = MagicMock()
        agent.provider = provider
        agent.system_prompt = "system"
        agent._last_result = None

        pipeline = SummaryPipeline(agent)
        clinical_json, rendered = await pipeline.run(_make_summary_input())

        assert isinstance(clinical_json, dict)
        assert clinical_json["confidence"] == 0.0  # empty scaffold default
        assert rendered == "Rendered Hebrew prose"


class TestSummaryPipelineWithModality:
    @pytest.mark.asyncio
    async def test_modality_prompt_module_in_extraction_system_prompt(self):
        """Modality pack's prompt_module should appear in the extraction system prompt."""
        mock_pack = MagicMock()
        mock_pack.prompt_module = "## CBT FRAMEWORK\nFocus on cognitive model."
        mock_pack.label = "CBT"

        clinical_data = {"session_focus": "test", "confidence": 0.8, "key_themes": []}
        agent = _make_agent_with_two_responses(clinical_data, "CBT summary prose")
        pipeline = SummaryPipeline(agent)

        inp = SummaryInput(
            raw_content="session notes",
            client_name="דוד",
            session_number=1,
            session_date=date(2026, 1, 1),
            last_approved_summary=None,
            open_tasks=[],
            modality_pack=mock_pack,
            therapist_signature=None,
        )
        await pipeline.run(inp)

        first_call_msgs = agent.provider.generate.call_args_list[0].kwargs["messages"]
        system_content = next(m["content"] for m in first_call_msgs if m["role"] == "system")
        assert "CBT FRAMEWORK" in system_content


# ── _assemble_summary_input (unit test using mock DB) ─────────────────────────

class TestAssembleSummaryInput:
    def _make_session(self, patient_id=1, session_number=5, session_id=10):
        s = MagicMock()
        s.id = session_id
        s.patient_id = patient_id
        s.session_number = session_number
        s.session_date = date(2026, 3, 6)
        return s

    def _make_service_with_db(self, query_results: dict):
        """Create a SessionService with a mock DB that returns predetermined query results."""
        from app.services.session_service import SessionService

        db = MagicMock()

        def query_side_effect(model):
            q = MagicMock()
            key = model.__name__ if hasattr(model, "__name__") else str(model)
            q.filter.return_value.first.return_value = query_results.get(key)
            q.join.return_value.filter.return_value.order_by.return_value.first.return_value = \
                query_results.get(f"{key}_joined")
            q.filter.return_value.all.return_value = query_results.get(f"{key}_all", [])
            return q

        db.query.side_effect = query_side_effect

        service = SessionService.__new__(SessionService)
        service.db = db
        return service

    @pytest.mark.asyncio
    async def test_uses_only_approved_summaries_for_last_approved(self):
        """The assembler must NOT use draft summaries as last_approved_summary."""
        from app.services.session_service import SessionService
        from app.models.session import SessionSummary

        session = self._make_session()
        agent = MagicMock()
        agent.modality_pack = None

        # Mock: approved summary exists
        approved_summary = MagicMock(spec=SessionSummary)
        approved_summary.full_summary = "Previously approved text"
        approved_summary.approved_by_therapist = True

        db = MagicMock()

        def query_side_effect(model):
            q = MagicMock()
            # Patient query
            from app.models.patient import Patient
            if model is Patient:
                patient = MagicMock()
                patient.full_name_encrypted = None
                q.filter.return_value.first.return_value = patient
            elif model is SessionSummary:
                # joined query: returns approved summary
                q.join.return_value.filter.return_value.order_by.return_value.first.return_value = (
                    approved_summary
                )
            else:
                # Exercise
                q.filter.return_value.all.return_value = []
            return q

        db.query.side_effect = query_side_effect

        service = SessionService.__new__(SessionService)
        service.db = db

        with patch("app.services.session_service.SignatureEngine") as MockSig:
            MockSig.return_value.get_active_profile = AsyncMock(return_value=None)
            result = await service._assemble_summary_input(session, "Notes", agent)

        # Should have populated last_approved_summary from the approved row
        assert result.last_approved_summary == "Previously approved text"

    @pytest.mark.asyncio
    async def test_no_approved_summaries_gives_none(self):
        from app.services.session_service import SessionService
        from app.models.session import SessionSummary

        session = self._make_session()
        agent = MagicMock()
        agent.modality_pack = None

        db = MagicMock()

        def query_side_effect(model):
            q = MagicMock()
            from app.models.patient import Patient
            if model is Patient:
                patient = MagicMock()
                patient.full_name_encrypted = None
                q.filter.return_value.first.return_value = patient
            elif model is SessionSummary:
                # No approved summary found
                q.join.return_value.filter.return_value.order_by.return_value.first.return_value = None
            else:
                q.filter.return_value.all.return_value = []
            return q

        db.query.side_effect = query_side_effect

        service = SessionService.__new__(SessionService)
        service.db = db

        with patch("app.services.session_service.SignatureEngine") as MockSig:
            MockSig.return_value.get_active_profile = AsyncMock(return_value=None)
            result = await service._assemble_summary_input(session, "Notes", agent)

        assert result.last_approved_summary is None

    @pytest.mark.asyncio
    async def test_open_tasks_populated_from_exercises(self):
        from app.services.session_service import SessionService
        from app.models.session import SessionSummary
        from app.models.exercise import Exercise

        session = self._make_session()
        agent = MagicMock()
        agent.modality_pack = None

        exercise1 = MagicMock(spec=Exercise)
        exercise1.description = "לנהל יומן מחשבות"
        exercise2 = MagicMock(spec=Exercise)
        exercise2.description = "תרגול נשימה"

        db = MagicMock()

        def query_side_effect(model):
            q = MagicMock()
            from app.models.patient import Patient
            if model is Patient:
                patient = MagicMock()
                patient.full_name_encrypted = None
                q.filter.return_value.first.return_value = patient
            elif model is SessionSummary:
                q.join.return_value.filter.return_value.order_by.return_value.first.return_value = None
            elif model is Exercise:
                q.filter.return_value.all.return_value = [exercise1, exercise2]
            else:
                q.filter.return_value.all.return_value = []
            return q

        db.query.side_effect = query_side_effect

        service = SessionService.__new__(SessionService)
        service.db = db

        with patch("app.services.session_service.SignatureEngine") as MockSig:
            MockSig.return_value.get_active_profile = AsyncMock(return_value=None)
            result = await service._assemble_summary_input(session, "Notes", agent)

        assert "לנהל יומן מחשבות" in result.open_tasks
        assert "תרגול נשימה" in result.open_tasks


# ── CLINICAL_JSON_SCHEMA shape ────────────────────────────────────────────────

class TestClinicalJsonSchema:
    def test_required_keys_present(self):
        required = {
            "session_focus", "key_themes", "interventions_used", "client_response",
            "homework_reviewed", "automatic_thoughts", "cognitive_distortions",
            "new_homework", "mood_observed", "risk_assessment",
            "next_session_focus", "longitudinal_note", "confidence",
        }
        assert required.issubset(set(CLINICAL_JSON_SCHEMA.keys()))

    def test_homework_reviewed_is_nested(self):
        hw = CLINICAL_JSON_SCHEMA["homework_reviewed"]
        assert isinstance(hw, dict)
        assert "was_reviewed" in hw
        assert "completed" in hw
        assert "barriers" in hw

    def test_risk_assessment_is_nested(self):
        risk = CLINICAL_JSON_SCHEMA["risk_assessment"]
        assert isinstance(risk, dict)
        assert "risk_present" in risk
        assert "notes" in risk

    def test_automatic_thoughts_and_distortions_are_lists(self):
        assert isinstance(CLINICAL_JSON_SCHEMA["automatic_thoughts"], list)
        assert isinstance(CLINICAL_JSON_SCHEMA["cognitive_distortions"], list)
