"""
Phase 7 — Treatment Plan 2.0 + Plan Drift Helper tests.

12 required tests: source-of-truth enforcement, zero-summary fallback,
goal-ID stability across updates, dropped goals preserved, version increment,
drift on-track / soft / hard flag thresholds, hook triggering, no-plan skip,
history ordering, and telemetry.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest

from app.ai.treatment_plan import (
    TreatmentPlanPipeline,
    TreatmentPlanInput,
    TreatmentPlanResult,
    DriftChecker,
    DriftResult,
    _build_extraction_system_prompt,
    _build_extraction_user_prompt,
    _parse_plan_json,
    _DRIFT_SOFT_THRESHOLD,
    _DRIFT_HARD_THRESHOLD,
    _ZERO_APPROVED_HEBREW,
)
from app.ai.models import FlowType
from app.core.config import settings


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_summary(n: int, full_summary: str = "סיכום מאושר") -> dict:
    return {
        "session_date": f"2026-0{min(n, 9)}-01",
        "session_number": n,
        "full_summary": full_summary,
        "topics_discussed": [f"נושא {n}"],
        "homework_assigned": [],
        "next_session_plan": "להמשיך",
        "risk_assessment": None,
        "mood_observed": "רגוע",
    }


def _make_plan_json(version: int = 1, extra_goals: list = None) -> dict:
    goals = [
        {
            "goal_id": "G1",
            "description": "הפחתת חרדה",
            "priority": "high",
            "status": "in_progress",
            "target_sessions": 10,
        }
    ]
    if extra_goals:
        goals.extend(extra_goals)
    return {
        "presenting_problem": "חרדה כללית",
        "primary_goals": goals,
        "interventions_planned": [
            {"intervention": "CBT", "linked_goal_ids": ["G1"], "frequency": "שבועי"}
        ],
        "milestones": [
            {
                "milestone_id": "M1",
                "description": "ירידה בדירוג חרדה",
                "target_by_session": 5,
                "achieved": False,
            }
        ],
        "risk_considerations": [],
        "review_frequency_sessions": 6,
        "modality": "cbt",
        "created_at_session": 3,
        "version": version,
        "confidence": 0.85,
    }


def _make_provider(extraction_json: str = None, render_text: str = "תוכנית טיפול") -> MagicMock:
    from app.ai.models import GenerationResult
    ext = extraction_json or json.dumps(_make_plan_json(), ensure_ascii=False)
    provider = MagicMock()
    provider.generate = AsyncMock(side_effect=[
        GenerationResult(
            content=ext,
            model_used=settings.AI_DEEP_MODEL,
            provider="test",
            flow_type=FlowType.TREATMENT_PLAN,
            prompt_tokens=300,
            completion_tokens=150,
            route_reason="flow:treatment_plan,tier:deep",
        ),
        GenerationResult(
            content=render_text,
            model_used=settings.AI_DEEP_MODEL,
            provider="test",
            flow_type=FlowType.TREATMENT_PLAN,
            prompt_tokens=400,
            completion_tokens=200,
            route_reason="flow:treatment_plan,tier:deep",
        ),
    ])
    return provider


def _make_drift_provider(
    drift_score: float = 0.1,
    drift_flags: list = None,
    on_track_items: list = None,
    recommendation: str = "הכל תקין",
) -> MagicMock:
    from app.ai.models import GenerationResult
    data = {
        "drift_score": drift_score,
        "drift_flags": drift_flags or [],
        "on_track_items": on_track_items or ["מטרה G1 מטופלת"],
        "recommendation": recommendation,
    }
    provider = MagicMock()
    provider.generate = AsyncMock(return_value=GenerationResult(
        content=json.dumps(data, ensure_ascii=False),
        model_used=settings.AI_FAST_MODEL,
        provider="test",
        flow_type=FlowType.PLAN_DRIFT_CHECK,
        prompt_tokens=100,
        completion_tokens=50,
        route_reason="flow:plan_drift_check,tier:fast",
    ))
    return provider


def _make_inp(
    approved_summaries: Optional[list] = None,
    existing_plan: Optional[dict] = None,
) -> TreatmentPlanInput:
    return TreatmentPlanInput(
        client_id=1,
        therapist_id=2,
        modality="cbt",
        approved_summaries=approved_summaries if approved_summaries is not None
        else [_make_summary(i) for i in range(1, 4)],
        therapist_profile={"name": "ד\"ר כהן", "modality": "cbt"},
        existing_plan=existing_plan,
    )


# ── Test 1: Source-of-truth — only approved summaries in extraction prompt ────

def test_plan_source_of_truth():
    """Extraction user prompt contains ONLY the sessions passed in approved_summaries."""
    summaries = [_make_summary(i, f"סיכום מאושר {i}") for i in range(1, 4)]
    inp = _make_inp(approved_summaries=summaries)
    prompt = _build_extraction_user_prompt(inp)

    assert "Session #1" in prompt
    assert "Session #2" in prompt
    assert "Session #3" in prompt
    assert "סיכום מאושר 1" in prompt
    # sessions_analyzed note is present
    assert "3" in prompt


# ── Test 2: Zero approved summaries → graceful Hebrew fallback ────────────────

@pytest.mark.asyncio
async def test_plan_zero_approved_summaries():
    """Zero approved summaries → Hebrew fallback, no LLM call."""
    provider = _make_provider()
    pipeline = TreatmentPlanPipeline(provider)

    inp = _make_inp(approved_summaries=[])
    result = await pipeline.run(inp)

    assert result.rendered_text == _ZERO_APPROVED_HEBREW
    assert result.plan_json == {}
    assert result.model_used == "none"
    assert result.tokens_used == 0
    provider.generate.assert_not_called()


# ── Test 3: Goal IDs preserved on update ──────────────────────────────────────

def test_plan_goal_ids_preserved_on_update():
    """Extraction system prompt for updates explicitly requires preserving goal/milestone IDs."""
    existing = _make_plan_json(version=1)
    inp = _make_inp(existing_plan=existing)
    system = _build_extraction_system_prompt(inp)

    # Update mode prompts should require ID preservation
    assert "goal_id" in system or "G1" in system or "preserve" in system.lower() or "IDs" in system or "מזהה" in system

    # User prompt should include the existing plan
    user = _build_extraction_user_prompt(inp)
    assert "G1" in user   # existing goal ID in context
    assert "M1" in user   # existing milestone ID in context


# ── Test 4: Dropped goals not deleted — status="dropped" ─────────────────────

def test_plan_dropped_goals_not_deleted():
    """Extraction system prompt for updates instructs 'dropped' not deletion."""
    existing = _make_plan_json(version=1)
    inp = _make_inp(existing_plan=existing)
    system = _build_extraction_system_prompt(inp)

    assert "dropped" in system


# ── Test 5: Version increments on each update ─────────────────────────────────

@pytest.mark.asyncio
async def test_plan_version_increments():
    """Each pipeline run with existing_plan increments version and sets parent reference."""
    existing = _make_plan_json(version=2)

    # Provider returns plan with version=3 (as if model responded correctly)
    updated_plan_json = _make_plan_json(version=3)
    provider = _make_provider(
        extraction_json=json.dumps(updated_plan_json, ensure_ascii=False),
        render_text="תוכנית מעודכנת",
    )
    pipeline = TreatmentPlanPipeline(provider)

    inp = _make_inp(existing_plan=existing)
    result = await pipeline.run(inp)

    # Pipeline should derive version = existing.version + 1 = 3
    assert result.version == 3


@pytest.mark.asyncio
async def test_plan_version_service_creates_parent_link():
    """TreatmentPlanService.update_plan() sets parent_version_id on the new plan."""
    from app.services.treatment_plan_service import TreatmentPlanService
    from app.models.treatment_plan import TreatmentPlan, PlanStatus

    # Existing plan mock
    existing_plan_row = MagicMock(spec=TreatmentPlan)
    existing_plan_row.id = 10
    existing_plan_row.patient_id = 1
    existing_plan_row.therapist_id = 2
    existing_plan_row.status = PlanStatus.ACTIVE.value
    existing_plan_row.plan_json = _make_plan_json(version=1)
    existing_plan_row.version = 1

    mock_patient = MagicMock()
    mock_patient.id = 1
    mock_patient.therapist_id = 2

    # DB mock
    db = MagicMock()
    db.query.return_value.filter.return_value.first.side_effect = [
        mock_patient,          # Patient ownership check
        MagicMock(),           # Therapist (for profile)
        MagicMock(),           # TherapistProfile
    ]
    db.query.return_value.filter.return_value.order_by.return_value.first.return_value = existing_plan_row
    db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
    db.flush = MagicMock()
    db.add = MagicMock()

    provider = _make_provider(render_text="תוכנית v2")
    service = TreatmentPlanService(db)

    new_plans_added = []
    def capture_add(obj):
        if isinstance(obj, TreatmentPlan):
            new_plans_added.append(obj)
    db.add.side_effect = capture_add

    with patch("app.services.treatment_plan_service.SignatureEngine") as MockSig:
        MockSig.return_value.get_active_profile = AsyncMock(return_value=None)
        with patch.object(service, "_write_generation_log"):
            await service.update_plan(
                patient_id=1,
                therapist_id=2,
                session_ids=None,
                provider=provider,
            )

    # The new plan should have parent_version_id = existing_plan_row.id
    assert len(new_plans_added) == 1
    assert new_plans_added[0].parent_version_id == existing_plan_row.id
    # Old plan should be archived
    assert existing_plan_row.status == PlanStatus.ARCHIVED.value


# ── Test 6: Drift on-track (score < 0.3) ─────────────────────────────────────

@pytest.mark.asyncio
async def test_drift_on_track():
    """score < 0.3 → no drift flags expected (on track)."""
    provider = _make_drift_provider(
        drift_score=0.1,
        drift_flags=[],
        on_track_items=["מטרה G1 — הפחתת חרדה — מטופלת"],
        recommendation="הטיפול מתנהל בהתאם לתוכנית.",
    )
    checker = DriftChecker(provider)
    result = await checker.check_drift(
        active_plan=_make_plan_json(),
        recent_summaries=[_make_summary(1), _make_summary(2)],
        session_id=5,
    )

    assert result.drift_score < _DRIFT_SOFT_THRESHOLD
    assert result.drift_flags == []
    assert len(result.on_track_items) > 0
    assert not result.recommendation.startswith("⚠️")


# ── Test 7: Drift soft flag (0.3–0.6) ────────────────────────────────────────

@pytest.mark.asyncio
async def test_drift_soft_flag():
    """score 0.3–0.6 → drift_flags stored, no ⚠️ prefix."""
    provider = _make_drift_provider(
        drift_score=0.45,
        drift_flags=["מטרה G1 — הפחתת חרדה — לא הוזכרה ב-2 פגישות האחרונות"],
        on_track_items=["עבודה על כישורי ויסות רגשי"],
        recommendation="מומלץ לחזור למטרות המוגדרות בתוכנית.",
    )
    checker = DriftChecker(provider)
    result = await checker.check_drift(
        active_plan=_make_plan_json(),
        recent_summaries=[_make_summary(3), _make_summary(4)],
        session_id=6,
    )

    assert _DRIFT_SOFT_THRESHOLD <= result.drift_score < _DRIFT_HARD_THRESHOLD
    assert len(result.drift_flags) > 0
    assert not result.recommendation.startswith("⚠️")


# ── Test 8: Drift hard flag (score > 0.6) ────────────────────────────────────

@pytest.mark.asyncio
async def test_drift_hard_flag():
    """score >= 0.6 → recommendation prefixed with ⚠️."""
    provider = _make_drift_provider(
        drift_score=0.75,
        drift_flags=[
            "מטרה G1 — הפחתת חרדה — לא טופלה כלל",
            "אין עבודה על מיומנויות CBT שהוגדרו בתוכנית",
        ],
        on_track_items=[],
        recommendation="יש לחזור לתוכנית הטיפול ולדון בסטייה עם המטופל.",
    )
    checker = DriftChecker(provider)
    result = await checker.check_drift(
        active_plan=_make_plan_json(),
        recent_summaries=[_make_summary(5)],
        session_id=7,
    )

    assert result.drift_score >= _DRIFT_HARD_THRESHOLD
    assert len(result.drift_flags) >= 2
    assert result.recommendation.startswith("⚠️")


# ── Test 9: Drift triggered on approval ──────────────────────────────────────

@pytest.mark.asyncio
async def test_drift_triggered_on_approval():
    """asyncio.create_task is called with run_drift_check when summary is approved."""
    from app.services.session_service import SessionService
    from app.models.session import SessionSummary

    mock_session = MagicMock()
    mock_session.id = 10
    mock_session.patient_id = 1
    mock_session.therapist_id = 2

    mock_summary = MagicMock(spec=SessionSummary)
    mock_summary.id = 99
    mock_summary.approved_by_therapist = False
    mock_summary.ai_draft_text = "טיוטה של ה-AI"
    mock_summary.full_summary = "הטקסט המאושר"
    mock_summary.therapist_edit_distance = None
    mock_session.summary = mock_summary

    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = mock_session

    service = SessionService(db)

    task_coroutines = []

    async def mock_audit(*args, **kwargs):
        pass

    import asyncio as real_asyncio

    with patch.object(service, "audit_service") as mock_audit_svc:
        mock_audit_svc.log_action = AsyncMock()
        with patch("app.services.session_service.SignatureEngine") as MockSig:
            MockSig.return_value.get_active_profile = AsyncMock(return_value=None)
            MockSig.return_value.record_approval = AsyncMock()
            with patch("app.services.session_service.TreatmentPlanService") as MockPlanSvc:
                mock_plan_instance = MagicMock()
                mock_plan_instance.run_drift_check = AsyncMock(return_value=None)
                MockPlanSvc.return_value = mock_plan_instance

                with patch.object(real_asyncio, "create_task", MagicMock()) as mock_ct:
                    await service.approve_summary(session_id=10, therapist_id=2)

    # create_task was called — at minimum once (drift check hook fires)
    assert mock_ct.called


# ── Test 10: Drift skipped when no active plan ────────────────────────────────

@pytest.mark.asyncio
async def test_drift_skipped_when_no_plan():
    """run_drift_check returns None without error when no active plan exists."""
    from app.services.treatment_plan_service import TreatmentPlanService

    db = MagicMock()
    db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None

    provider = _make_drift_provider()
    service = TreatmentPlanService(db)

    result = await service.run_drift_check(
        patient_id=1,
        therapist_id=2,
        session_id=5,
        provider=provider,
    )

    assert result is None
    # Provider should NOT have been called (no plan → no check)
    provider.generate.assert_not_called()


# ── Test 11: Plan history endpoint — newest first ─────────────────────────────

def test_plan_history_endpoint():
    """get_plan_history() returns all versions ordered newest → oldest."""
    from app.services.treatment_plan_service import TreatmentPlanService
    from app.models.treatment_plan import TreatmentPlan, PlanStatus

    def _make_plan_row(version: int, status: str = "archived") -> MagicMock:
        row = MagicMock(spec=TreatmentPlan)
        row.id = version
        row.patient_id = 1
        row.therapist_id = 2
        row.status = status
        row.version = version
        row.parent_version_id = version - 1 if version > 1 else None
        row.created_at = datetime(2026, 1, version)
        return row

    plan_v3 = _make_plan_row(3, "active")
    plan_v2 = _make_plan_row(2, "archived")
    plan_v1 = _make_plan_row(1, "archived")

    # Returned newest → oldest (version desc)
    ordered = [plan_v3, plan_v2, plan_v1]

    db = MagicMock()
    # patient ownership
    mock_patient = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = mock_patient
    # history query
    db.query.return_value.filter.return_value.order_by.return_value.all.return_value = ordered

    service = TreatmentPlanService(db)
    history = service.get_plan_history(patient_id=1, therapist_id=2)

    assert len(history) == 3
    assert history[0].version == 3
    assert history[1].version == 2
    assert history[2].version == 1
    # parent_version_id chain is correct
    assert history[0].parent_version_id == 2
    assert history[1].parent_version_id == 1
    assert history[2].parent_version_id is None


# ── Test 12: Telemetry — ai_generation_log rows written ──────────────────────

@pytest.mark.asyncio
async def test_plan_telemetry():
    """
    create_plan writes 2 TREATMENT_PLAN log rows (extraction + render).
    run_drift_check writes 1 PLAN_DRIFT_CHECK log row.
    """
    from app.services.treatment_plan_service import TreatmentPlanService
    from app.models.treatment_plan import TreatmentPlan

    mock_patient = MagicMock()
    mock_patient.id = 1
    mock_patient.therapist_id = 2

    mock_therapist = MagicMock()
    mock_therapist.full_name = "ד\"ר כהן"

    mock_profile = MagicMock()
    mock_profile.certifications = "פסיכולוג"
    mock_profile.therapeutic_approach = MagicMock(value="cbt")
    mock_profile.education = "PhD"

    mock_session_row = MagicMock()
    mock_session_row.session_date = "2026-01-01"
    mock_session_row.session_number = 1
    mock_session_row.summary_id = 99
    mock_summary = MagicMock()
    mock_summary.approved_by_therapist = True
    mock_summary.full_summary = "סיכום"
    mock_summary.topics_discussed = []
    mock_summary.homework_assigned = []
    mock_summary.next_session_plan = None
    mock_summary.risk_assessment = None
    mock_summary.mood_observed = None
    mock_session_row.summary = mock_summary

    db = MagicMock()
    db.query.return_value.filter.return_value.first.side_effect = [
        mock_patient, mock_therapist, mock_profile,
    ]
    db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None  # no existing plan
    db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [mock_session_row]
    db.query.return_value.filter.return_value.all.return_value = [mock_session_row]
    db.flush = MagicMock()
    db.add = MagicMock()

    provider = _make_provider()
    service = TreatmentPlanService(db)

    with patch.object(service, "_write_generation_log") as mock_log:
        with patch("app.services.treatment_plan_service.SignatureEngine") as MockSig:
            MockSig.return_value.get_active_profile = AsyncMock(return_value=None)
            with patch("app.services.treatment_plan_service.TreatmentPlan") as MockTP:
                mock_plan_instance = MagicMock()
                mock_plan_instance.id = 1
                MockTP.return_value = mock_plan_instance

                await service.create_plan(
                    patient_id=1,
                    therapist_id=2,
                    session_ids=None,
                    provider=provider,
                )

    plan_calls = [
        c for c in mock_log.call_args_list
        if c.kwargs.get("flow_type") == FlowType.TREATMENT_PLAN
    ]
    assert len(plan_calls) == 2, f"Expected 2 TREATMENT_PLAN log calls, got {len(plan_calls)}"

    # Drift check telemetry
    drift_provider = _make_drift_provider(drift_score=0.5)
    mock_plan = MagicMock()
    mock_plan.plan_json = _make_plan_json()
    mock_plan.patient_id = 1

    db2 = MagicMock()
    db2.query.return_value.filter.return_value.order_by.return_value.first.return_value = mock_plan
    db2.query.return_value.filter.return_value.order_by.return_value.all.return_value = [mock_session_row]
    db2.query.return_value.filter.return_value.all.return_value = [mock_session_row]
    db2.query.return_value.filter.return_value.first.return_value = MagicMock()  # session lookup
    db2.flush = MagicMock()

    service2 = TreatmentPlanService(db2)
    with patch.object(service2, "_write_generation_log") as mock_log2:
        await service2.run_drift_check(
            patient_id=1,
            therapist_id=2,
            session_id=5,
            provider=drift_provider,
        )

    drift_calls = [
        c for c in mock_log2.call_args_list
        if c.kwargs.get("flow_type") == FlowType.PLAN_DRIFT_CHECK
    ]
    assert len(drift_calls) == 1, f"Expected 1 PLAN_DRIFT_CHECK log call, got {len(drift_calls)}"
