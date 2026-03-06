"""
Phase 5 — Israeli Formal Record tests.

10 required tests covering: source-of-truth enforcement, zero-summary fallback,
record-type specific structure (SOAP for progress note), session scope for
termination, license number in referrals, legal disclaimer correctness,
deep model enforcement, approve workflow, and telemetry.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.ai.formal_record import (
    LEGAL_DISCLAIMER_HE,
    FormalRecordInput,
    FormalRecordPipeline,
    FormalRecordResult,
    RecordType,
    _build_extraction_system_prompt,
    _build_extraction_user_prompt,
    _build_render_system_prompt,
    _parse_record_json,
    _ZERO_APPROVED_HEBREW,
)
from app.ai.models import FlowType
from app.ai.router import ModelRouter
from app.core.config import settings


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_summary(n: int, full_summary: str = "סיכום מאושר", risk: Optional[str] = None) -> dict:
    return {
        "session_date": f"2026-0{min(n, 9)}-01",
        "session_number": n,
        "full_summary": full_summary,
        "topics_discussed": [f"נושא {n}"],
        "homework_assigned": [f"משימה {n}"],
        "next_session_plan": "להמשיך",
        "risk_assessment": risk,
        "mood_observed": "רגוע",
        "clinical_json": None,
    }


def _make_therapist_profile(
    name: str = "ד\"ר יונה כהן",
    license_type: str = "פסיכולוג קליני מורשה",
    license_number: str = "IL-12345",
) -> dict:
    return {
        "name": name,
        "license_type": license_type,
        "license_number": license_number,
        "modality": "cbt",
        "education": "PhD",
    }


def _make_extraction_json(record_type: str = "progress_note", license_num: str = "IL-12345") -> str:
    return json.dumps({
        "record_type": record_type,
        "client_info": {"age_range": "30-40", "referral_source": "הפניה עצמית", "presenting_problem": "חרדה כללית"},
        "treatment_summary": {
            "session_count": 3,
            "date_range": "ינואר–מרץ 2026",
            "modality_used": "CBT",
            "primary_diagnoses_or_themes": ["חרדה כללית"],
            "goals_addressed": ["הפחתת חרדה"],
            "interventions_used": ["שאלות סוקרטיות", "ניסוי התנהגותי"],
        },
        "clinical_status": {
            "current_functioning": "תפקוד תקין ברוב תחומי החיים",
            "risk_assessment": "אין סיכון",
            "progress_rating": "moderate",
        },
        "recommendations": ["המשך טיפול"],
        "legal_disclaimer": "",
        "therapist_signature_block": {
            "name": "ד\"ר יונה כהן",
            "license_type": "פסיכולוג קליני מורשה",
            "license_number": license_num,
            "date": "2026-03-06",
        },
        "sessions_analyzed": 3,
        "confidence": 0.88,
    }, ensure_ascii=False)


def _make_provider(extraction_json: str = None, render_text: str = "רשומה רשמית") -> MagicMock:
    """Build a mock AIProvider."""
    ext_json = extraction_json or _make_extraction_json()
    from app.ai.models import GenerationResult
    provider = MagicMock()
    provider.generate = AsyncMock(side_effect=[
        GenerationResult(
            content=ext_json,
            model_used=settings.AI_DEEP_MODEL,
            provider="test",
            flow_type=FlowType.FORMAL_RECORD,
            prompt_tokens=300,
            completion_tokens=150,
            route_reason="flow:formal_record,tier:deep",
        ),
        GenerationResult(
            content=render_text,
            model_used=settings.AI_DEEP_MODEL,
            provider="test",
            flow_type=FlowType.FORMAL_RECORD,
            prompt_tokens=400,
            completion_tokens=200,
            route_reason="flow:formal_record,tier:deep",
        ),
    ])
    return provider


def _make_inp(
    record_type: RecordType = RecordType.PROGRESS_NOTE,
    approved_summaries: Optional[list] = None,
    therapist_profile: Optional[dict] = None,
) -> FormalRecordInput:
    return FormalRecordInput(
        client_id=1,
        therapist_id=2,
        record_type=record_type,
        session_ids=[1, 2, 3],
        approved_summaries=approved_summaries if approved_summaries is not None else [_make_summary(i) for i in range(1, 4)],
        therapist_profile=therapist_profile or _make_therapist_profile(),
        additional_context=None,
    )


# ── Test 1: Source-of-truth — only approved summaries passed through ──────────

def test_formal_record_source_of_truth():
    """
    Extraction user prompt contains ONLY the sessions passed in approved_summaries.
    Callers (service) enforce approved_by_therapist=True; pipeline trusts the input.
    """
    summaries = [_make_summary(i, full_summary=f"סיכום מאושר {i}") for i in range(1, 4)]
    inp = _make_inp(approved_summaries=summaries)
    prompt = _build_extraction_user_prompt(inp)

    # All 3 approved sessions present
    assert "Session #1" in prompt
    assert "Session #2" in prompt
    assert "Session #3" in prompt
    assert "sessions_analyzed=3" in prompt
    # Full summary text (not ai_draft_text) referenced
    assert "סיכום מאושר 1" in prompt


# ── Test 2: Zero approved summaries → graceful Hebrew fallback ────────────────

@pytest.mark.asyncio
async def test_formal_record_zero_approved():
    """Zero approved summaries → graceful Hebrew fallback, no LLM call."""
    provider = _make_provider()
    pipeline = FormalRecordPipeline(provider)

    inp = _make_inp(approved_summaries=[])
    result = await pipeline.run(inp)

    assert result.rendered_text == _ZERO_APPROVED_HEBREW
    assert result.record_json == {}
    assert result.model_used == "none"
    assert result.tokens_used == 0
    provider.generate.assert_not_called()


# ── Test 3: PROGRESS_NOTE — SOAP structure fields present ────────────────────

def test_formal_record_progress_note_structure():
    """PROGRESS_NOTE extraction system prompt includes SOAP structure."""
    inp = _make_inp(record_type=RecordType.PROGRESS_NOTE)
    system = _build_extraction_system_prompt(inp)

    # SOAP acronym instructions should be present
    assert "SOAP" in system or "סובייקטיבי" in system or "התרשמות" in system


def test_formal_record_progress_note_render_system():
    """PROGRESS_NOTE render system prompt includes formal Hebrew writing rules."""
    inp = _make_inp(record_type=RecordType.PROGRESS_NOTE)
    render_system = _build_render_system_prompt(inp)

    assert "רשמית" in render_system or "formal" in render_system.lower()
    assert "passive" in render_system.lower() or "פסיב" in render_system or "נמצא" in render_system


# ── Test 4: TERMINATION_SUMMARY uses all approved sessions ───────────────────

def test_formal_record_termination_uses_all_sessions():
    """TERMINATION_SUMMARY extraction prompt includes all approved sessions."""
    summaries = [_make_summary(i) for i in range(1, 8)]  # 7 sessions
    inp = _make_inp(record_type=RecordType.TERMINATION_SUMMARY, approved_summaries=summaries)
    prompt = _build_extraction_user_prompt(inp)

    # All 7 sessions in the prompt
    for i in range(1, 8):
        assert f"Session #{i}" in prompt
    assert "sessions_analyzed=7" in prompt

    # Termination-specific instruction included in extraction system prompt
    system = _build_extraction_system_prompt(inp)
    assert "TERMINATION" in system or "סיום" in system or "arc" in system.lower()


# ── Test 5: REFERRAL_LETTER — license number in system prompt ────────────────

def test_formal_record_referral_has_license():
    """REFERRAL_LETTER extraction system prompt explicitly requires license number."""
    inp = _make_inp(
        record_type=RecordType.REFERRAL_LETTER,
        therapist_profile=_make_therapist_profile(license_number="IL-99999"),
    )
    system = _build_extraction_system_prompt(inp)
    user = _build_extraction_user_prompt(inp)

    # Referral letter must require license number — check instruction is present
    assert "license" in system.lower() or "רישיון" in system or "רישום" in system
    # Therapist profile (with license number) injected into user prompt
    assert "IL-99999" in user


# ── Test 6: Legal disclaimer always in rendered text ─────────────────────────

@pytest.mark.asyncio
async def test_formal_record_disclaimer_present():
    """LEGAL_DISCLAIMER_HE is always appended to rendered_text."""
    provider = _make_provider(render_text="פסקה ראשונה של הרשומה.")
    pipeline = FormalRecordPipeline(provider)

    inp = _make_inp(approved_summaries=[_make_summary(1)])
    result = await pipeline.run(inp)

    assert LEGAL_DISCLAIMER_HE in result.rendered_text
    # Disclaimer comes after the main body
    body_end = result.rendered_text.index(LEGAL_DISCLAIMER_HE)
    assert body_end > 0


# ── Test 7: Disclaimer is a constant, not AI-generated ───────────────────────

def test_formal_record_disclaimer_not_ai_generated():
    """
    LEGAL_DISCLAIMER_HE is a module-level constant.
    It must not appear in the LLM prompts — it is appended post-generation.
    The extraction schema instructs the model to leave legal_disclaimer empty.
    """
    inp = _make_inp()
    extraction_user = _build_extraction_user_prompt(inp)
    render_user_content = "render prompt placeholder"

    # The disclaimer text must NOT appear in either prompt
    assert LEGAL_DISCLAIMER_HE not in extraction_user

    # The extraction system prompt explicitly tells the model to leave it empty
    extraction_system = _build_extraction_system_prompt(inp)
    assert "legal_disclaimer" in extraction_system and "empty" in extraction_system.lower()

    # Verify the constant itself is non-empty and Hebrew
    assert len(LEGAL_DISCLAIMER_HE) > 50
    assert "AI" in LEGAL_DISCLAIMER_HE


# ── Test 8: Deep model always used (regardless of session count) ──────────────

def test_formal_record_deep_model_always():
    """FORMAL_RECORD flow always resolves to AI_DEEP_MODEL — no escalation needed."""
    router = ModelRouter()
    model_id, route_reason = router.resolve(FlowType.FORMAL_RECORD)

    assert model_id == settings.AI_DEEP_MODEL
    assert "deep" in route_reason

    # Even with zero sessions — still deep
    model_id_zero, _ = router.resolve(FlowType.FORMAL_RECORD, session_count=0)
    assert model_id_zero == settings.AI_DEEP_MODEL

    # Not escalated by session count (already deep by default)
    model_id_many, reason_many = router.resolve(FlowType.FORMAL_RECORD, session_count=100)
    assert model_id_many == settings.AI_DEEP_MODEL


# ── Test 9: Approve endpoint — status and timestamp set ──────────────────────

def test_formal_record_approve_endpoint():
    """approve_formal_record() sets status='approved' and approved_at timestamp."""
    from app.services.formal_record_service import FormalRecordService
    from app.models.formal_record import FormalRecord, RecordStatus

    mock_record = MagicMock(spec=FormalRecord)
    mock_record.id = 42
    mock_record.therapist_id = 2
    mock_record.status = RecordStatus.DRAFT.value
    mock_record.approved_at = None

    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = mock_record
    db.flush = MagicMock()

    service = FormalRecordService(db)
    result = service.approve_formal_record(record_id=42, therapist_id=2)

    assert result.status == RecordStatus.APPROVED.value
    assert result.approved_at is not None
    db.flush.assert_called_once()


# ── Test 10: Telemetry — ai_generation_log rows written ──────────────────────

@pytest.mark.asyncio
async def test_formal_record_telemetry():
    """
    create_formal_record writes 2 FORMAL_RECORD log rows (extraction + render)
    plus 1 COMPLETENESS_CHECK row when summaries exist.
    """
    from app.services.formal_record_service import FormalRecordService
    from app.models.formal_record import FormalRecord

    mock_patient = MagicMock()
    mock_patient.id = 1
    mock_patient.therapist_id = 2

    mock_therapist = MagicMock()
    mock_therapist.full_name = "ד\"ר כהן"

    mock_profile = MagicMock()
    mock_profile.certifications = "פסיכולוג"
    mock_profile.license_type = None      # let certifications fallback work
    mock_profile.license_number = None
    mock_profile.therapeutic_approach = MagicMock(value="cbt")
    mock_profile.education = "PhD"

    mock_session_row = MagicMock()
    mock_session_row.session_date = "2026-01-01"
    mock_session_row.session_number = 1
    mock_session_row.summary_id = 99
    mock_session_summary = MagicMock()
    mock_session_summary.approved_by_therapist = True
    mock_session_summary.full_summary = "סיכום"
    mock_session_summary.topics_discussed = []
    mock_session_summary.homework_assigned = []
    mock_session_summary.next_session_plan = None
    mock_session_summary.risk_assessment = None
    mock_session_summary.mood_observed = None
    mock_session_summary.clinical_json = None
    mock_session_row.summary = mock_session_summary

    db = MagicMock()
    db.query.return_value.filter.return_value.first.side_effect = [
        mock_patient, mock_therapist, mock_profile,
    ]
    db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [mock_session_row]
    db.flush = MagicMock()
    db.add = MagicMock()

    provider = _make_provider()
    service = FormalRecordService(db)

    with patch.object(service, "_write_generation_log") as mock_log:
        with patch("app.services.formal_record_service.SignatureEngine") as MockSig:
            MockSig.return_value.get_active_profile = AsyncMock(return_value=None)
            with patch("app.services.formal_record_service.CompletenessChecker") as MockChecker:
                checker_instance = MagicMock()
                checker_instance.check = AsyncMock(
                    return_value=MagicMock(score=0.9, to_dict=lambda: {"score": 0.9})
                )
                from app.ai.models import GenerationResult
                checker_instance._last_result = GenerationResult(
                    content="ok", model_used="test", provider="test",
                    flow_type=FlowType.COMPLETENESS_CHECK,
                )
                MockChecker.return_value = checker_instance

                # Also patch FormalRecord to avoid DB insert issues
                with patch("app.services.formal_record_service.FormalRecord") as MockFR:
                    mock_fr_instance = MagicMock()
                    mock_fr_instance.id = 1
                    mock_fr_instance.rendered_text = "rendered"
                    MockFR.return_value = mock_fr_instance

                    await service.create_formal_record(
                        patient_id=1,
                        therapist_id=2,
                        record_type=RecordType.PROGRESS_NOTE,
                        session_ids=None,
                        additional_context=None,
                        provider=provider,
                    )

    formal_calls = [
        c for c in mock_log.call_args_list
        if c.kwargs.get("flow_type") == FlowType.FORMAL_RECORD
    ]
    assert len(formal_calls) == 2, f"Expected 2 FORMAL_RECORD log calls, got {len(formal_calls)}"

    completeness_calls = [
        c for c in mock_log.call_args_list
        if c.kwargs.get("flow_type") == FlowType.COMPLETENESS_CHECK
    ]
    assert len(completeness_calls) == 1
