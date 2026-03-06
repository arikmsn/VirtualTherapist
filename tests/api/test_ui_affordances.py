"""
Phase 9 — UI Affordances + Edit Tracking tests.

10 tests:
 1. AI_ERRORS_HE keys present and non-empty
 2. AIMeta dataclass has required fields with correct defaults
 3. get_ai_health — returns ai_ready=True when approved summaries exist
 4. get_ai_health — returns ai_ready=False + correct counts when no approved summaries
 5. get_ai_health — 404 when patient not owned by therapist
 6. get_drift_alerts — returns only plans with drift_score >= 0.3, ordered descending
 7. get_signature_progress — is_active=False below threshold
 8. get_signature_progress — is_active=True at or above threshold + progress_pct capped at 100
 9. edit_start — sets edit_started_at on first call; subsequent calls are idempotent
10. edit_save — increments therapist_edit_count; 409 if already approved
"""

from __future__ import annotations

import dataclasses
from datetime import datetime, timezone
from typing import Optional
from unittest.mock import MagicMock, patch

import pytest

from app.api.errors import AI_ERRORS_HE, AIMeta
from app.api.routes.ui_affordances import (
    get_ai_health,
    get_drift_alerts,
    get_signature_progress,
    edit_start,
    edit_save,
    _get_owned_summary,
)
from fastapi import HTTPException


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _make_therapist(therapist_id: int = 1) -> MagicMock:
    t = MagicMock()
    t.id = therapist_id
    return t


def _make_summary_orm(
    summary_id: int = 10,
    approved: bool = False,
    edit_count: int = 0,
    edit_started: Optional[datetime] = None,
    completeness: Optional[float] = None,
    edit_distance: Optional[int] = None,
) -> MagicMock:
    s = MagicMock()
    s.id = summary_id
    s.approved_by_therapist = approved
    s.therapist_edit_count = edit_count
    s.edit_started_at = edit_started
    s.edit_ended_at = None
    s.completeness_score = completeness
    s.therapist_edit_distance = edit_distance
    return s


def _make_plan(
    plan_id: int,
    patient_id: int,
    drift_score: float,
    drift_flags: list,
    last_check: Optional[datetime] = None,
) -> MagicMock:
    p = MagicMock()
    p.id = plan_id
    p.patient_id = patient_id
    p.drift_score = drift_score
    p.drift_flags = drift_flags
    p.last_drift_check_at = last_check
    p.status = "active"
    return p


def _make_signature(
    approved_count: int,
    min_req: int = 5,
    style_summary: Optional[str] = None,
) -> MagicMock:
    s = MagicMock()
    s.approved_sample_count = approved_count
    s.min_samples_required = min_req
    s.style_summary = style_summary
    return s


def _make_db() -> MagicMock:
    return MagicMock()


# ── Test 1: AI_ERRORS_HE ─────────────────────────────────────────────────────

def test_ai_errors_he_keys_present():
    required_keys = [
        "no_approved_summaries",
        "client_not_found",
        "summary_not_found",
        "plan_not_found",
        "deep_summary_not_found",
        "ai_generation_failed",
        "signature_not_active",
        "no_active_plan",
        "edit_already_started",
        "summary_already_approved",
    ]
    for key in required_keys:
        assert key in AI_ERRORS_HE, f"Missing key: {key}"
        assert AI_ERRORS_HE[key].strip(), f"Empty message for key: {key}"


# ── Test 2: AIMeta dataclass ──────────────────────────────────────────────────

def test_ai_meta_defaults():
    meta = AIMeta(model_used="claude-haiku", tokens_used=500, generation_time_ms=1200)
    assert meta.model_used == "claude-haiku"
    assert meta.tokens_used == 500
    assert meta.generation_time_ms == 1200
    assert meta.completeness_score is None
    assert meta.confidence is None
    assert meta.signature_applied is False
    assert meta.ai_layer_version == "9.0"
    # Must be serialisable as dict (used in route responses)
    d = dataclasses.asdict(meta)
    assert d["model_used"] == "claude-haiku"
    assert d["signature_applied"] is False


# ── Test 3: get_ai_health — ai_ready=True ────────────────────────────────────

def test_get_ai_health_ready(monkeypatch):
    db = _make_db()
    therapist = _make_therapist()

    approved = _make_summary_orm(approved=True, completeness=0.85, edit_distance=12)
    draft = _make_summary_orm(approved=False)

    # Patch _owns_patient → True
    monkeypatch.setattr("app.api.routes.ui_affordances._owns_patient", lambda *a, **k: True)

    # Patch DB query chain for summaries
    query_mock = MagicMock()
    query_mock.join.return_value.filter_by.return_value.all.return_value = [approved, draft]
    # Subsequent queries for has_deep / has_plan / has_vault / signature
    sub = MagicMock()
    sub.filter_by.return_value.first.return_value = None
    query_mock2 = MagicMock()
    query_mock2.filter_by.return_value.first.return_value = None

    call_count = [0]
    def _query_side_effect(model):
        call_count[0] += 1
        if call_count[0] == 1:  # first call: summaries
            return query_mock
        return query_mock2

    db.query.side_effect = _query_side_effect

    result = get_ai_health(client_id=5, current_therapist=therapist, db=db)

    assert result.ai_ready is True
    assert result.approved_summaries == 1
    assert result.draft_summaries == 1
    assert result.avg_completeness_score == pytest.approx(0.85)
    assert result.avg_edit_distance == pytest.approx(12.0)


# ── Test 4: get_ai_health — no approved summaries ────────────────────────────

def test_get_ai_health_not_ready(monkeypatch):
    db = _make_db()
    therapist = _make_therapist()

    draft = _make_summary_orm(approved=False)

    monkeypatch.setattr("app.api.routes.ui_affordances._owns_patient", lambda *a, **k: True)

    query_mock = MagicMock()
    query_mock.join.return_value.filter_by.return_value.all.return_value = [draft]
    sub = MagicMock()
    sub.filter_by.return_value.first.return_value = None

    call_count = [0]
    def _q(model):
        call_count[0] += 1
        if call_count[0] == 1:
            return query_mock
        return sub

    db.query.side_effect = _q

    result = get_ai_health(client_id=5, current_therapist=therapist, db=db)

    assert result.ai_ready is False
    assert result.approved_summaries == 0
    assert result.draft_summaries == 1
    assert result.avg_completeness_score is None
    assert result.avg_edit_distance is None


# ── Test 5: get_ai_health — 404 on unowned patient ───────────────────────────

def test_get_ai_health_404_unowned(monkeypatch):
    db = _make_db()
    therapist = _make_therapist()

    monkeypatch.setattr("app.api.routes.ui_affordances._owns_patient", lambda *a, **k: False)

    with pytest.raises(HTTPException) as exc_info:
        get_ai_health(client_id=999, current_therapist=therapist, db=db)

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == AI_ERRORS_HE["client_not_found"]


# ── Test 6: get_drift_alerts — ordered by drift_score descending ──────────────

def test_get_drift_alerts_ordering(monkeypatch):
    db = _make_db()
    therapist = _make_therapist()

    plan_low = _make_plan(plan_id=1, patient_id=10, drift_score=0.35, drift_flags=["flag A"])
    plan_high = _make_plan(plan_id=2, patient_id=20, drift_score=0.78, drift_flags=["flag B", "flag C"])

    # Mock query chain: single .filter(...) call with multiple conditions, then .order_by(...).all()
    query = MagicMock()
    query.filter.return_value.order_by.return_value.all.return_value = [plan_high, plan_low]
    db.query.return_value = query

    monkeypatch.setattr(
        "app.api.routes.ui_affordances._get_patient_name",
        lambda db, pid: f"מטופל {pid}",
    )

    result = get_drift_alerts(current_therapist=therapist, db=db)

    assert result.total == 2
    assert result.alerts[0].drift_score == pytest.approx(0.78)
    assert result.alerts[0].plan_id == 2
    assert result.alerts[1].drift_score == pytest.approx(0.35)
    assert result.alerts[0].drift_flags == ["flag B", "flag C"]


# ── Test 7: get_signature_progress — not yet active ──────────────────────────

def test_get_signature_progress_not_active():
    db = _make_db()
    therapist = _make_therapist()

    # Signature row exists but below threshold
    sig = _make_signature(approved_count=3, min_req=5)

    query = MagicMock()
    query.filter_by.return_value.first.return_value = sig
    db.query.return_value = query

    result = get_signature_progress(current_therapist=therapist, db=db)

    assert result.is_active is False
    assert result.approved_summary_count == 3
    assert result.min_samples_required == 5
    assert result.progress_pct == pytest.approx(60.0)
    assert result.style_summary is None


# ── Test 8: get_signature_progress — active + progress capped at 100 ─────────

def test_get_signature_progress_active_and_capped():
    db = _make_db()
    therapist = _make_therapist()

    sig = _make_signature(approved_count=12, min_req=5, style_summary="מטפל ממוקד וישיר")

    query = MagicMock()
    query.filter_by.return_value.first.return_value = sig
    db.query.return_value = query

    result = get_signature_progress(current_therapist=therapist, db=db)

    assert result.is_active is True
    assert result.progress_pct == pytest.approx(100.0)   # capped
    assert result.style_summary == "מטפל ממוקד וישיר"


# ── Test 9: edit_start — idempotent ──────────────────────────────────────────

def test_edit_start_idempotent(monkeypatch):
    db = _make_db()
    therapist = _make_therapist()

    ts = datetime(2026, 3, 6, 10, 0, 0)
    summary = _make_summary_orm(edit_started=ts)

    monkeypatch.setattr(
        "app.api.routes.ui_affordances._get_owned_summary",
        lambda db, sid, tid: summary,
    )

    result = edit_start(summary_id=10, current_therapist=therapist, db=db)

    # edit_started_at already set — should not change it and not commit
    assert result.edit_started_at == ts
    db.commit.assert_not_called()


def test_edit_start_sets_timestamp(monkeypatch):
    db = _make_db()
    therapist = _make_therapist()

    summary = _make_summary_orm(edit_started=None)
    summary.id = 10

    monkeypatch.setattr(
        "app.api.routes.ui_affordances._get_owned_summary",
        lambda db, sid, tid: summary,
    )

    before = datetime.utcnow()
    result = edit_start(summary_id=10, current_therapist=therapist, db=db)
    after = datetime.utcnow()

    assert result.summary_id == 10
    assert summary.edit_started_at is not None
    assert before <= summary.edit_started_at <= after
    db.commit.assert_called_once()


# ── Test 10: edit_save — increment + 409 on approved ─────────────────────────

def test_edit_save_increments(monkeypatch):
    db = _make_db()
    therapist = _make_therapist()

    summary = _make_summary_orm(approved=False, edit_count=2)
    summary.id = 10

    monkeypatch.setattr(
        "app.api.routes.ui_affordances._get_owned_summary",
        lambda db, sid, tid: summary,
    )

    result = edit_save(summary_id=10, current_therapist=therapist, db=db)

    assert result.therapist_edit_count == 3
    db.commit.assert_called_once()


def test_edit_save_409_if_approved(monkeypatch):
    db = _make_db()
    therapist = _make_therapist()

    summary = _make_summary_orm(approved=True, edit_count=1)

    monkeypatch.setattr(
        "app.api.routes.ui_affordances._get_owned_summary",
        lambda db, sid, tid: summary,
    )

    with pytest.raises(HTTPException) as exc_info:
        edit_save(summary_id=10, current_therapist=therapist, db=db)

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == AI_ERRORS_HE["summary_already_approved"]
