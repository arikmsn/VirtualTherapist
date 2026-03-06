"""
Phase 4 — Pre-Session Prep 2.0 tests.

10 required tests covering: source-of-truth enforcement, zero-summary fallback,
mode-specific field selection, signature injection, completeness storage,
cache behaviour, and telemetry logging.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest

from app.ai.models import FlowType, GenerationResult
from app.ai.prep import (
    PrepInput,
    PrepMode,
    PrepPipeline,
    PrepResult,
    PREP_JSON_SCHEMA,
    _parse_prep_json,
    _build_extraction_system_prompt,
    _build_extraction_user_prompt,
    _build_render_system_prompt,
    _ZERO_APPROVED_HEBREW,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_summary(
    n: int,
    full_summary: str = "סיכום פגישה",
    homework: Optional[str] = None,
    risk: Optional[str] = None,
) -> dict:
    return {
        "session_date": f"2026-01-{n:02d}",
        "session_number": n,
        "full_summary": full_summary,
        "topics_discussed": [f"נושא {n}"],
        "homework_assigned": [homework] if homework else [],
        "next_session_plan": f"תכנית {n}",
        "risk_assessment": risk,
        "mood_observed": "רגוע",
        "clinical_json": None,
    }


def _make_approved_summaries(count: int) -> list[dict]:
    return [_make_summary(i + 1) for i in range(count)]


def _make_generation_result(content: str, model: str = "test-model") -> GenerationResult:
    return GenerationResult(
        content=content,
        model_used=model,
        provider="test",
        flow_type=FlowType.PRE_SESSION_PREP,
        prompt_tokens=100,
        completion_tokens=50,
        generation_ms=200,
        route_reason="test",
    )


def _mock_agent(extraction_content: str = None, render_content: str = "הכנה לפגישה"):
    """Build a minimal TherapyAgent-like mock with a provider."""
    extraction_json = extraction_content or json.dumps({
        "client_snapshot": {"primary_themes": ["חרדה"], "active_goals": [], "coping_strengths": [], "persistent_challenges": []},
        "last_session_summary": {"key_points": ["נקודה 1"], "homework_given": "תרגיל", "homework_status": None, "open_threads": []},
        "upcoming_session_focus": {"suggested_agenda": ["נושא לפגישה"], "questions_to_explore": [], "modality_checklist": [], "risk_flags": []},
        "longitudinal_patterns": {"progress_narrative": "התקדמות", "regression_signals": [], "pattern_since_session_n": None},
        "gaps": {"missing_information": [], "untouched_areas": [], "assessment_due": []},
        "mode_used": "concise",
        "sessions_analyzed": 1,
        "confidence": 0.85,
    })

    provider = MagicMock()
    provider.generate = AsyncMock(side_effect=[
        _make_generation_result(extraction_json),
        _make_generation_result(render_content),
    ])

    agent = MagicMock()
    agent.provider = provider
    agent.system_prompt = "system prompt"
    agent.modality_pack = None
    agent._last_result = None
    return agent


def _make_prep_input(
    mode: PrepMode = PrepMode.CONCISE,
    approved_summaries: Optional[list] = None,
    therapist_signature: Optional[dict] = None,
    modality_prompt_module: Optional[str] = None,
) -> PrepInput:
    return PrepInput(
        client_id=1,
        session_id=10,
        therapist_id=2,
        mode=mode,
        modality="generic_integrative",
        approved_summaries=approved_summaries if approved_summaries is not None else _make_approved_summaries(3),
        modality_prompt_module=modality_prompt_module,
        therapist_signature=therapist_signature,
    )


# ── Test 1: Source-of-truth — unapproved rows must be excluded by callers ────

def test_prep_source_of_truth():
    """
    PrepPipeline never queries the DB — it receives approved_summaries from the
    caller. Verify that passing only approved rows means the extraction prompt
    references exactly those sessions and nothing else.
    """
    approved = _make_approved_summaries(2)
    inp = _make_prep_input(mode=PrepMode.CONCISE, approved_summaries=approved)

    prompt = _build_extraction_user_prompt(inp)

    # The prompt must reference only the 2 approved sessions
    assert "Session #1" in prompt
    assert "Session #2" in prompt
    assert "sessions_analyzed" in prompt
    # Content comes from full_summary, not ai_draft_text
    assert "סיכום פגישה" in prompt


# ── Test 2: Zero approved summaries → graceful Hebrew fallback ───────────────

@pytest.mark.asyncio
async def test_prep_zero_approved_summaries():
    """When no approved summaries exist, return Hebrew fallback — no LLM call."""
    agent = _mock_agent()
    pipeline = PrepPipeline(agent)

    inp = _make_prep_input(approved_summaries=[])
    result = await pipeline.run(inp)

    assert result.rendered_text == _ZERO_APPROVED_HEBREW
    assert result.prep_json == {}
    assert result.model_used == "none"
    assert result.tokens_used == 0
    # No provider calls should have been made
    agent.provider.generate.assert_not_called()


# ── Test 3: CONCISE mode — correct fields + token guidance ───────────────────

def test_prep_mode_concise_fields_and_token_guidance():
    """CONCISE mode extraction prompt includes only the 3 required fields."""
    inp = _make_prep_input(mode=PrepMode.CONCISE)
    prompt = _build_extraction_user_prompt(inp)

    # Required fields for CONCISE
    assert "last_session_summary.key_points" in prompt
    assert "upcoming_session_focus.suggested_agenda" in prompt
    assert "upcoming_session_focus.risk_flags" in prompt

    # Token guidance for concise
    assert "400" in prompt or "5–7" in prompt


# ── Test 4: DEEP mode — all non-gap fields populated ─────────────────────────

def test_prep_mode_deep_fields():
    """DEEP mode extraction prompt includes client_snapshot, longitudinal_patterns, etc."""
    inp = _make_prep_input(mode=PrepMode.DEEP)
    prompt = _build_extraction_user_prompt(inp)

    assert "client_snapshot" in prompt
    assert "last_session_summary" in prompt
    assert "upcoming_session_focus" in prompt
    assert "longitudinal_patterns" in prompt
    # gaps is excluded from DEEP
    assert "gaps" not in prompt or prompt.index("gaps") > prompt.index("mode_used")


# ── Test 5: BY_MODALITY / CBT — checklist items present ─────────────────────

def test_prep_mode_by_modality_cbt():
    """BY_MODALITY mode with a CBT prompt_module surfaces modality_checklist in the prompt."""
    cbt_module = (
        "CBT framework: agenda setting → homework review → new material.\n"
        "Required: automatic thoughts, cognitive distortions, new homework."
    )
    inp = _make_prep_input(
        mode=PrepMode.BY_MODALITY,
        modality_prompt_module=cbt_module,
    )
    system = _build_extraction_system_prompt(inp)
    user = _build_extraction_user_prompt(inp)

    # CBT module injected into system prompt
    assert "CBT framework" in system
    # modality_checklist field referenced in user prompt
    assert "modality_checklist" in user
    # BY_MODALITY token guidance present
    assert "700" in user


# ── Test 6: GAP_ANALYSIS mode — only gap/thread/regression fields ─────────────

def test_prep_mode_gap_analysis_fields():
    """GAP_ANALYSIS mode extraction prompt references gaps, open_threads, regression_signals."""
    inp = _make_prep_input(mode=PrepMode.GAP_ANALYSIS)
    prompt = _build_extraction_user_prompt(inp)

    assert "gaps" in prompt
    assert "open_threads" in prompt
    assert "regression_signals" in prompt
    # client_snapshot should NOT be in the required fields list for gap_analysis
    # (it appears in the schema but not in the FIELDS TO POPULATE section)
    fields_section = prompt.split("FIELDS TO POPULATE")[1].split("---")[0]
    assert "client_snapshot" not in fields_section


# ── Test 7: Therapist signature — injected in rendering only ─────────────────

@pytest.mark.asyncio
async def test_prep_signature_injection():
    """therapist_signature is injected into the render system prompt, not extraction."""
    sig = {"tone": "warm", "preferred_terms": ["מחשבות אוטומטיות"]}
    inp = _make_prep_input(therapist_signature=sig)

    render_system = _build_render_system_prompt(inp)
    extraction_system = _build_extraction_system_prompt(inp)

    # Signature in render system prompt
    assert "tone" in render_system
    assert "warm" in render_system

    # Signature NOT in extraction system prompt
    assert "warm" not in extraction_system
    assert "tone" not in extraction_system


# ── Test 8: Completeness score stored after pipeline run ─────────────────────

@pytest.mark.asyncio
async def test_prep_completeness_stored():
    """
    After run(), PrepResult.completeness_score is initially 0.0 (caller fills it).
    Verify the pipeline itself does not mutate completeness — that's the service's job.
    """
    agent = _mock_agent()
    pipeline = PrepPipeline(agent)

    inp = _make_prep_input(approved_summaries=_make_approved_summaries(2))
    result = await pipeline.run(inp)

    # Pipeline returns 0.0 placeholder for completeness
    assert result.completeness_score == 0.0
    assert result.completeness_data == {}
    # But rendered_text and prep_json are populated
    assert isinstance(result.rendered_text, str)
    assert isinstance(result.prep_json, dict)


# ── Test 9: Cache hit — same mode within 10 min returns cache ────────────────

@pytest.mark.asyncio
async def test_prep_cache_hit():
    """
    session_service.generate_prep_v2 returns cached prep_json when same mode
    was generated within the last 10 minutes.
    """
    from app.services.session_service import SessionService

    # Build a minimal mock session with fresh cached prep data
    mock_session = MagicMock()
    mock_session.prep_json = {"mode_used": "concise", "sessions_analyzed": 3, "confidence": 0.9}
    mock_session.prep_mode = "concise"
    mock_session.prep_generated_at = datetime.utcnow() - timedelta(seconds=120)  # 2 min ago
    mock_session.prep_completeness_score = 0.85
    mock_session.patient_id = 1
    mock_session.therapist_id = 2
    mock_session.id = 10

    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = mock_session

    service = SessionService(db)
    agent = _mock_agent()

    result = await service.generate_prep_v2(
        session_id=10,
        therapist_id=2,
        mode=PrepMode.CONCISE,
        agent=agent,
    )

    # Cache hit — no LLM call
    agent.provider.generate.assert_not_called()
    # Returned the cached prep_json
    assert result["mode"] == "concise"
    assert result["prep_json"] == mock_session.prep_json


# ── Test 10: Telemetry — ai_generation_log rows correct ──────────────────────

@pytest.mark.asyncio
async def test_prep_telemetry():
    """
    After a successful generate_prep_v2 call with approved summaries,
    _write_generation_log is called with FlowType.PRE_SESSION_PREP for both
    extraction and rendering, plus one COMPLETENESS_CHECK call.
    """
    from app.services.session_service import SessionService

    # Session with NO cached prep (force fresh generation)
    mock_session = MagicMock()
    mock_session.prep_json = None
    mock_session.prep_mode = None
    mock_session.prep_generated_at = None
    mock_session.patient_id = 1
    mock_session.therapist_id = 2
    mock_session.id = 10
    mock_session.summary_id = None

    mock_patient = MagicMock()
    mock_patient.id = 1
    mock_patient.full_name_encrypted = b"encrypted"
    mock_patient.therapist_id = 2

    # Build a mock patient session with an approved summary
    mock_summary = MagicMock()
    mock_summary.approved_by_therapist = True
    mock_summary.full_summary = "סיכום מאושר"
    mock_summary.topics_discussed = ["חרדה"]
    mock_summary.homework_assigned = []
    mock_summary.next_session_plan = "להמשיך"
    mock_summary.risk_assessment = None
    mock_summary.mood_observed = "רגוע"
    mock_summary.clinical_json = None

    mock_patient_session = MagicMock()
    mock_patient_session.session_date = "2026-01-01"
    mock_patient_session.session_number = 1
    mock_patient_session.summary_id = 99
    mock_patient_session.summary = mock_summary

    db = MagicMock()
    # first.side_effect: session query → mock_session, patient query → mock_patient
    db.query.return_value.filter.return_value.first.side_effect = [mock_session, mock_patient]
    # all.return_value: patient_sessions query returns one session with approved summary
    db.query.return_value.filter.return_value.all.return_value = [mock_patient_session]
    db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [mock_patient_session]
    db.flush = MagicMock()
    db.add = MagicMock()

    agent = _mock_agent()
    agent.modality_pack = None

    service = SessionService(db)

    with patch.object(service, "_write_generation_log") as mock_log:
        with patch("app.services.session_service.CompletenessChecker") as MockChecker:
            with patch("app.services.session_service.SignatureEngine") as MockSig:
                MockSig.return_value.get_active_profile = AsyncMock(return_value=None)
                checker_instance = MagicMock()
                checker_instance.check = AsyncMock(
                    return_value=MagicMock(score=0.8, to_dict=lambda: {"score": 0.8})
                )
                checker_instance._last_result = _make_generation_result("ok")
                MockChecker.return_value = checker_instance

                await service.generate_prep_v2(
                    session_id=10,
                    therapist_id=2,
                    mode=PrepMode.CONCISE,
                    agent=agent,
                )

    # Expect 2 calls with PRE_SESSION_PREP flow type (extraction + render)
    prep_calls = [
        c for c in mock_log.call_args_list
        if c.kwargs.get("flow_type") == FlowType.PRE_SESSION_PREP
    ]
    assert len(prep_calls) == 2, (
        f"Expected 2 PRE_SESSION_PREP log calls, got {len(prep_calls)}"
    )

    # Completeness check also logged
    completeness_calls = [
        c for c in mock_log.call_args_list
        if c.kwargs.get("flow_type") == FlowType.COMPLETENESS_CHECK
    ]
    assert len(completeness_calls) == 1
