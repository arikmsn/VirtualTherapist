"""Tests for app/core/ai_context.py — build_ai_context_for_patient + format_protocol_block.

Covers:
  - No protocols anywhere → returns {}
  - Therapist-only protocols → therapist defaults used
  - Patient overrides therapist protocols
  - format_protocol_block: empty ctx → empty string
  - format_protocol_block: populated ctx → contains [AI_PROTOCOL_CONTEXT]
  - Prompt injection: each pipeline prompt contains [AI_PROTOCOL_CONTEXT] when protocols exist
"""

import json
import pytest
from unittest.mock import MagicMock

from app.core.ai_context import build_ai_context_for_patient, format_protocol_block
from app.ai.prep import _build_render_user_prompt, PrepInput, PrepMode
from app.ai.summary_pipeline import _build_render_prompt, SummaryInput
from app.ai.deep_summary import _build_synthesis_user, _build_render_user, DeepSummaryInput
from app.ai.treatment_plan import (
    _build_extraction_user_prompt,
    _build_render_user_prompt as _plan_render_prompt,
    TreatmentPlanInput,
)


# ---------------------------------------------------------------------------
# Helpers — lightweight mock objects
# ---------------------------------------------------------------------------

def _make_profile(
    protocols_used=None,
    custom_protocols=None,
    profession="psychologist",
    primary_therapy_modes=None,
    years_of_experience="8",
    areas_of_expertise="חרדה, ADHD",
):
    """Return a MagicMock that looks like a TherapistProfile ORM row."""
    p = MagicMock()
    p.profession = profession
    p.primary_therapy_modes = primary_therapy_modes or []
    p.years_of_experience = years_of_experience
    p.areas_of_expertise = areas_of_expertise
    p.protocols_used = protocols_used
    p.custom_protocols = custom_protocols
    return p


def _make_patient(protocol_ids=None, demographics=None):
    """Return a MagicMock that looks like a Patient ORM row."""
    pt = MagicMock()
    pt.protocol_ids = protocol_ids
    pt.demographics = demographics
    return pt


# ---------------------------------------------------------------------------
# build_ai_context_for_patient — no protocols
# ---------------------------------------------------------------------------


def test_no_protocols_returns_empty():
    profile = _make_profile(protocols_used=None, custom_protocols=None)
    patient = _make_patient(protocol_ids=None)
    ctx = build_ai_context_for_patient(profile, patient)
    assert ctx == {}, "Expected empty dict when no protocols exist"


def test_none_profile_returns_empty():
    ctx = build_ai_context_for_patient(None, None)
    assert ctx == {}


# ---------------------------------------------------------------------------
# Therapist-only defaults
# ---------------------------------------------------------------------------


def test_therapist_only_protocols():
    profile = _make_profile(
        protocols_used=["cbt_depression", "act_general"],
        primary_therapy_modes=["cbt", "act"],
    )
    patient = _make_patient(protocol_ids=None)
    ctx = build_ai_context_for_patient(profile, patient)

    assert ctx != {}
    assert ctx["therapist"]["profession"] == "psychologist"
    assert ctx["therapist"]["experience_years"] == 8
    assert "חרדה" in ctx["therapist"]["specialties"]

    active_ids = ctx["patient"]["protocol_ids"]
    assert "cbt_depression" in active_ids
    assert "act_general" in active_ids
    assert ctx["patient"]["primary_protocol_id"] == "cbt_depression"

    protocol_names = [p["id"] for p in ctx["protocols"]]
    assert "cbt_depression" in protocol_names
    assert "act_general" in protocol_names


# ---------------------------------------------------------------------------
# session_count → completed_sessions in protocol dicts
# ---------------------------------------------------------------------------


def test_session_count_adds_completed_sessions():
    profile = _make_profile(protocols_used=["cbt_depression"])
    patient = _make_patient(protocol_ids=None)
    ctx = build_ai_context_for_patient(profile, patient, session_count=5)
    for p in ctx["protocols"]:
        assert p.get("completed_sessions") == 5, f"Expected completed_sessions=5 in {p}"


def test_no_session_count_omits_completed_sessions():
    profile = _make_profile(protocols_used=["cbt_depression"])
    patient = _make_patient(protocol_ids=None)
    ctx = build_ai_context_for_patient(profile, patient)  # no session_count
    for p in ctx["protocols"]:
        assert "completed_sessions" not in p, f"completed_sessions should be absent: {p}"


# ---------------------------------------------------------------------------
# Patient overrides therapist
# ---------------------------------------------------------------------------


def test_patient_overrides_therapist():
    profile = _make_profile(protocols_used=["cbt_anxiety"])
    patient = _make_patient(protocol_ids=["cbt_depression", "dbt_skills"])

    ctx = build_ai_context_for_patient(profile, patient)

    active_ids = ctx["patient"]["protocol_ids"]
    assert "cbt_depression" in active_ids
    assert "dbt_skills" in active_ids
    # therapist default must NOT appear
    assert "cbt_anxiety" not in active_ids
    assert ctx["patient"]["primary_protocol_id"] == "cbt_depression"


def test_empty_patient_list_falls_back_to_therapist():
    """Empty list (not None) should fall back to therapist defaults (mirrors protocol_context logic)."""
    profile = _make_profile(protocols_used=["cbt_panic"])
    patient = _make_patient(protocol_ids=[])

    ctx = build_ai_context_for_patient(profile, patient)
    active_ids = ctx["patient"]["protocol_ids"]
    assert "cbt_panic" in active_ids


# ---------------------------------------------------------------------------
# Demographics
# ---------------------------------------------------------------------------


def test_demographics_injected():
    profile = _make_profile(protocols_used=["emdr_trauma"])
    patient = _make_patient(
        protocol_ids=None,
        demographics={"age": 35, "marital_status": "single", "has_guardian": False},
    )
    ctx = build_ai_context_for_patient(profile, patient)
    assert ctx["patient"]["age"] == 35
    assert ctx["patient"]["marital_status"] == "single"
    assert ctx["patient"]["has_guardian"] is False


# ---------------------------------------------------------------------------
# format_protocol_block
# ---------------------------------------------------------------------------


def test_format_empty_ctx_returns_empty_string():
    assert format_protocol_block({}) == ""
    assert format_protocol_block(None) == ""


def test_format_no_protocols_returns_empty_string():
    ctx = {"therapist": {}, "patient": {"protocol_ids": []}, "protocols": []}
    assert format_protocol_block(ctx) == ""


def test_format_with_protocols_contains_sentinel():
    profile = _make_profile(protocols_used=["cbt_depression"])
    patient = _make_patient(protocol_ids=None)
    ctx = build_ai_context_for_patient(profile, patient)

    block = format_protocol_block(ctx)
    assert "[AI_PROTOCOL_CONTEXT]" in block
    assert "[/AI_PROTOCOL_CONTEXT]" in block
    assert "cbt_depression" in block
    # Must be valid JSON inside the block
    start = block.index("[AI_PROTOCOL_CONTEXT]") + len("[AI_PROTOCOL_CONTEXT]")
    end = block.index("[/AI_PROTOCOL_CONTEXT]")
    json_str = block[start:end].strip()
    parsed = json.loads(json_str)
    assert "protocols" in parsed


def test_format_block_instructions_are_english():
    profile = _make_profile(protocols_used=["dbt_skills"])
    patient = _make_patient(protocol_ids=None)
    ctx = build_ai_context_for_patient(profile, patient)
    block = format_protocol_block(ctx)

    # The wrapper text must be English
    assert "Professional and protocol context" in block
    assert "Use this JSON ONLY as context" in block
    assert "fluent professional Hebrew" in block


# ---------------------------------------------------------------------------
# Prompt injection — each pipeline user prompt contains the block when protocols exist
# ---------------------------------------------------------------------------


def _ctx_with_protocols():
    profile = _make_profile(protocols_used=["cbt_depression"])
    patient = _make_patient(protocol_ids=None)
    return build_ai_context_for_patient(profile, patient)


def test_prep_render_prompt_contains_block():
    ctx = _ctx_with_protocols()
    inp = PrepInput(
        client_id=1,
        session_id=1,
        therapist_id=1,
        mode=PrepMode.DEEP,
        modality="cbt",
        approved_summaries=[{"session_number": 1, "session_date": "2025-01-01", "full_summary": "test"}],
        ai_context=ctx,
    )
    prompt = _build_render_user_prompt(inp, {"client_snapshot": {}})
    assert "[AI_PROTOCOL_CONTEXT]" in prompt


def test_prep_render_prompt_no_block_when_no_protocols():
    inp = PrepInput(
        client_id=1,
        session_id=1,
        therapist_id=1,
        mode=PrepMode.CONCISE,
        modality="cbt",
        approved_summaries=[],
        ai_context=None,
    )
    prompt = _build_render_user_prompt(inp, {})
    assert "[AI_PROTOCOL_CONTEXT]" not in prompt


def test_summary_render_prompt_contains_block():
    ctx = _ctx_with_protocols()
    inp = SummaryInput(
        raw_content="some notes",
        client_name="Test",
        session_number=1,
        session_date="2025-01-01",
        last_approved_summary=None,
        open_tasks=[],
        modality_pack=None,
        ai_context=ctx,
    )
    prompt = _build_render_prompt(inp, {"session_focus": "test"})
    assert "[AI_PROTOCOL_CONTEXT]" in prompt


def test_deep_summary_synthesis_prompt_contains_block():
    ctx = _ctx_with_protocols()
    inp = DeepSummaryInput(
        client_id=1,
        therapist_id=1,
        modality="cbt",
        approved_summaries=[{"session_number": 1, "session_date": "2025-01-01", "full_summary": "test"}],
        ai_context=ctx,
    )
    prompt = _build_synthesis_user([{"arc_narrative": "x"}], inp)
    assert "[AI_PROTOCOL_CONTEXT]" in prompt


def test_deep_summary_render_prompt_contains_block():
    ctx = _ctx_with_protocols()
    inp = DeepSummaryInput(
        client_id=1,
        therapist_id=1,
        modality="cbt",
        approved_summaries=[],
        ai_context=ctx,
    )
    prompt = _build_render_user({"arc_narrative": "x"}, None, inp)
    assert "[AI_PROTOCOL_CONTEXT]" in prompt


def test_treatment_plan_extraction_prompt_contains_block():
    ctx = _ctx_with_protocols()
    inp = TreatmentPlanInput(
        client_id=1,
        therapist_id=1,
        modality="cbt",
        approved_summaries=[{"session_number": 1, "session_date": "2025-01-01", "full_summary": "test"}],
        therapist_profile={"name": "Test", "modality": "cbt"},
        ai_context=ctx,
    )
    prompt = _build_extraction_user_prompt(inp)
    assert "[AI_PROTOCOL_CONTEXT]" in prompt


def test_treatment_plan_render_prompt_contains_block():
    ctx = _ctx_with_protocols()
    inp = TreatmentPlanInput(
        client_id=1,
        therapist_id=1,
        modality="cbt",
        approved_summaries=[],
        therapist_profile={"name": "Test", "modality": "cbt"},
        ai_context=ctx,
    )
    prompt = _plan_render_prompt(inp, {"presenting_problem": "test", "primary_goals": []})
    assert "[AI_PROTOCOL_CONTEXT]" in prompt


def test_prompts_have_no_block_when_no_protocols():
    """When ai_context is empty, no pipeline prompt must include [AI_PROTOCOL_CONTEXT]."""
    for inp_cls, prompt_fn, extra in [
        (
            lambda: _build_render_user_prompt(
                PrepInput(
                    client_id=1, session_id=1, therapist_id=1,
                    mode=PrepMode.CONCISE, modality="generic",
                    approved_summaries=[], ai_context=None,
                ),
                {},
            ),
            None, None,
        ),
        (
            lambda: _build_render_prompt(
                SummaryInput(
                    raw_content="x", client_name="T", session_number=1,
                    session_date="2025-01-01", last_approved_summary=None,
                    open_tasks=[], modality_pack=None, ai_context=None,
                ),
                {},
            ),
            None, None,
        ),
        (
            lambda: _build_synthesis_user(
                [],
                DeepSummaryInput(
                    client_id=1, therapist_id=1, modality="cbt",
                    approved_summaries=[], ai_context=None,
                ),
            ),
            None, None,
        ),
        (
            lambda: _plan_render_prompt(
                TreatmentPlanInput(
                    client_id=1, therapist_id=1, modality="cbt",
                    approved_summaries=[], therapist_profile={},
                    ai_context=None,
                ),
                {},
            ),
            None, None,
        ),
    ]:
        prompt = inp_cls()
        assert "[AI_PROTOCOL_CONTEXT]" not in prompt
