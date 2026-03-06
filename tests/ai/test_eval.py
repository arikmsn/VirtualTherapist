"""
Phase 10 — Evaluation Framework tests.

10 tests:
 1. test_smoke_test_passes_with_valid_data      — 5 good samples → passed=True
 2. test_smoke_test_fails_low_completeness      — sample below 0.6 → passed=False
 3. test_regression_detected_when_delta_exceeds — delta > 0.1 → flagged
 4. test_regression_not_flagged_within_threshold — delta 0.05 → no flag
 5. test_no_baseline_skips_regression_check    — first run ever → no regression
 6. test_eval_run_stored_to_db                 — AIEvalRun row written
 7. test_eval_samples_stored_per_sample        — AIEvalSample rows written
 8. test_therapist_rating_stored               — rating + comment saved
 9. test_eval_dashboard_returns_full_schema    — all keys present
10. test_health_endpoint_includes_ai_layer_status — smoke test result in /health
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.ai.eval import (
    AIEvaluator,
    EvalConfig,
    EvalRunType,
    _hash_input,
    _safe_mean,
    SampleResult,
)
from app.ai.models import FlowType
from fastapi import HTTPException


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_summary_orm(
    summary_id: int = 1,
    completeness: float = 0.85,
    confidence_int: int = 80,   # stored 0–100 on the model
    edit_distance: int = 10,
    approved: bool = True,
    ai_draft: str = "טיוטת AI",
    full_summary: str = "סיכום מאושר",
) -> MagicMock:
    s = MagicMock()
    s.id = summary_id
    s.approved_by_therapist = approved
    s.completeness_score = completeness
    s.ai_confidence = confidence_int
    s.therapist_edit_distance = edit_distance
    s.ai_draft_text = ai_draft
    s.full_summary = full_summary
    s.session = MagicMock()
    s.session.id = 100 + summary_id
    return s


def _make_eval_run_row(
    run_id: int = 1,
    run_type: str = "smoke_test",
    flow_type: str = "session_summary",
    passed: bool = True,
    mean_comp: float = 0.82,
    mean_conf: float = 0.78,
    regression: bool = False,
    run_at: Optional[datetime] = None,
) -> MagicMock:
    r = MagicMock()
    r.id = run_id
    r.run_type = run_type
    r.flow_type = flow_type
    r.passed = passed
    r.mean_completeness = mean_comp
    r.mean_confidence = mean_conf
    r.mean_edit_distance = 12.0
    r.mean_therapist_rating = None
    r.regression_detected = regression
    r.regression_details = {}
    r.run_at = run_at or datetime(2026, 3, 6, 10, 0, 0)
    r.duration_ms = 120
    return r


def _make_db_with_summaries(summaries: list) -> MagicMock:
    """Build a DB mock that returns `summaries` from the summary query chain.

    The eval code uses a single .filter(...) call with multiple conditions:
      db.query(SessionSummary)
        .filter(cond1, cond2)
        .order_by(...)
        .limit(n)
        .all()
    """
    db = MagicMock()
    # Summary query chain (first call)
    summary_qm = MagicMock()
    summary_qm.filter.return_value.order_by.return_value.limit.return_value.all.return_value = summaries

    # Baseline query chain (second call, for get_baseline → returns None = no baseline)
    baseline_qm = MagicMock()
    baseline_qm.filter.return_value.order_by.return_value.first.return_value = None

    call_count = [0]

    def _q(*args, **kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            return summary_qm
        return baseline_qm

    db.query.side_effect = _q
    db.flush = MagicMock()
    db.add = MagicMock()
    db.commit = MagicMock()
    return db


# ── Test 1: Smoke test passes with valid data ─────────────────────────────────

@pytest.mark.asyncio
async def test_smoke_test_passes_with_valid_data():
    """5 samples with completeness >= 0.6 and confidence >= 0.7 → passed=True."""
    summaries = [_make_summary_orm(i, completeness=0.85, confidence_int=80) for i in range(1, 6)]
    db = _make_db_with_summaries(summaries)

    evaluator = AIEvaluator(db)
    result = await evaluator.run_smoke_test()

    assert result.passed is True
    assert result.sample_size == 5
    assert result.mean_completeness == pytest.approx(0.85)
    # confidence 80/100 = 0.8, above 0.7 threshold
    assert result.mean_confidence == pytest.approx(0.80)


# ── Test 2: Smoke test fails on low completeness ──────────────────────────────

@pytest.mark.asyncio
async def test_smoke_test_fails_low_completeness():
    """A sample with completeness 0.4 (below 0.6) makes the run fail."""
    good = [_make_summary_orm(i, completeness=0.85, confidence_int=80) for i in range(1, 5)]
    bad = _make_summary_orm(5, completeness=0.4, confidence_int=75)
    summaries = good + [bad]

    db = _make_db_with_summaries(summaries)
    evaluator = AIEvaluator(db)
    result = await evaluator.run_smoke_test()

    assert result.passed is False


# ── Test 3: Regression detected when delta exceeds threshold ──────────────────

def test_regression_detected_when_delta_exceeds_threshold():
    """
    Baseline comp=0.85, current comp=0.70 → delta=-0.15, exceeds max_delta=0.1 → flagged.
    """
    baseline = {"mean_completeness": 0.85, "mean_confidence": 0.80}
    result = AIEvaluator.compare_to_baseline(
        current_comp=0.70,
        current_conf=0.78,
        baseline=baseline,
        max_delta=0.1,
    )
    assert result["regression_detected"] is True
    metrics = result["metrics"]
    assert any(m["metric"] == "completeness" for m in metrics)
    comp_metric = next(m for m in metrics if m["metric"] == "completeness")
    assert comp_metric["delta"] == pytest.approx(-0.15, abs=0.001)


# ── Test 4: Regression not flagged within threshold ───────────────────────────

def test_regression_not_flagged_within_threshold():
    """Baseline comp=0.85, current=0.82 → delta=-0.03, within threshold → no flag."""
    baseline = {"mean_completeness": 0.85, "mean_confidence": 0.80}
    result = AIEvaluator.compare_to_baseline(
        current_comp=0.82,
        current_conf=0.78,
        baseline=baseline,
        max_delta=0.1,
    )
    assert result["regression_detected"] is False
    assert result["metrics"] == []


# ── Test 5: No baseline → no regression check performed ──────────────────────

@pytest.mark.asyncio
async def test_no_baseline_skips_regression_check():
    """
    First run ever: get_baseline returns None → regression_detected stays False.
    """
    summaries = [_make_summary_orm(i) for i in range(1, 4)]
    db = _make_db_with_summaries(summaries)

    config = EvalConfig(
        run_type=EvalRunType.REGRESSION,
        flow_type=FlowType.SESSION_SUMMARY,
        sample_size=3,
    )
    evaluator = AIEvaluator(db)

    # get_baseline returns None (no prior passing run)
    with patch.object(evaluator, "get_baseline", AsyncMock(return_value=None)):
        result = await evaluator.run_eval(config)

    assert result.regression_detected is False


# ── Test 6: Eval run row stored in DB ────────────────────────────────────────

@pytest.mark.asyncio
async def test_eval_run_stored_to_db():
    """AIEvalRun row is db.add()ed and db.commit()ed."""
    from app.models.eval import AIEvalRun

    summaries = [_make_summary_orm(i) for i in range(1, 4)]
    db = _make_db_with_summaries(summaries)

    added_rows = []

    def capture_add(obj):
        added_rows.append(obj)

    db.add = capture_add

    # Make flush set the id on the run row (first non-sample added)
    run_holder = [None]

    def _flush():
        for row in added_rows:
            if hasattr(row, "run_type") and not hasattr(row, "eval_run_id"):
                row.id = 42
                run_holder[0] = row

    db.flush = _flush

    config = EvalConfig(
        run_type=EvalRunType.SMOKE_TEST,
        flow_type=FlowType.SESSION_SUMMARY,
        sample_size=3,
    )
    evaluator = AIEvaluator(db)
    result = await evaluator.run_eval(config)

    # At least one AIEvalRun-like object was added
    run_rows = [r for r in added_rows if hasattr(r, "run_type") and not hasattr(r, "eval_run_id")]
    assert len(run_rows) >= 1
    db.commit.assert_called_once()


# ── Test 7: Eval sample rows stored per sample ───────────────────────────────

@pytest.mark.asyncio
async def test_eval_samples_stored_per_sample():
    """One AIEvalSample row is added per input summary."""
    from app.models.eval import AIEvalSample

    n = 3
    summaries = [_make_summary_orm(i) for i in range(1, n + 1)]
    db = _make_db_with_summaries(summaries)

    added_rows = []
    run_row_holder = [None]

    def capture_add(obj):
        added_rows.append(obj)
        if hasattr(obj, "run_type") and not hasattr(obj, "eval_run_id"):
            run_row_holder[0] = obj

    def _flush():
        if run_row_holder[0] is not None:
            run_row_holder[0].id = 99
        # Also handle the case where add hasn't been called yet


    db.add = capture_add
    db.flush = _flush

    config = EvalConfig(
        run_type=EvalRunType.SMOKE_TEST,
        flow_type=FlowType.SESSION_SUMMARY,
        sample_size=n,
    )
    evaluator = AIEvaluator(db)
    await evaluator.run_eval(config)

    sample_rows = [r for r in added_rows if hasattr(r, "eval_run_id")]
    assert len(sample_rows) == n


# ── Test 8: Therapist rating stored ──────────────────────────────────────────

def test_therapist_rating_stored():
    """POST /summaries/{id}/rate stores rating + comment + rated_at."""
    from app.api.routes.eval import rate_summary, RateSummaryRequest

    db = MagicMock()
    therapist = MagicMock()
    therapist.id = 1

    summary = MagicMock()
    summary.id = 10
    summary.rated_at = None

    with patch("app.api.routes.eval._get_owned_summary", return_value=summary):
        request = RateSummaryRequest(rating=4, comment="מאוד טוב")
        result = rate_summary(
            summary_id=10,
            request=request,
            current_therapist=therapist,
            db=db,
        )

    assert summary.therapist_rating == 4
    assert summary.therapist_rating_comment == "מאוד טוב"
    assert summary.rated_at is not None
    db.commit.assert_called_once()
    assert result.rating == 4


# ── Test 9: Eval dashboard returns full schema ────────────────────────────────

def test_eval_dashboard_returns_full_schema():
    """get_eval_dashboard returns all required top-level keys."""
    from app.api.routes.eval import get_eval_dashboard

    db = MagicMock()
    therapist = MagicMock()
    therapist.id = 1

    # last smoke test query
    smoke_row = _make_eval_run_row()
    smoke_qm = MagicMock()
    smoke_qm.filter.return_value.order_by.return_value.first.return_value = smoke_row

    # summaries aggregate query
    agg_qm = MagicMock()
    agg_qm.join.return_value.filter.return_value = agg_qm
    agg_qm.count.return_value = 10
    agg_qm.filter.return_value = agg_qm  # chained
    agg_qm.with_entities.return_value.first.return_value = (0.82, 80.0, 12.0, 4.2)

    # flow-type group-by
    flow_qm = MagicMock()
    flow_row = MagicMock()
    flow_row.flow_type = "session_summary"
    flow_row.gen_count = 8
    flow_row.avg_comp = 0.82
    flow_row.any_regression = False
    flow_qm.filter.return_value.group_by.return_value.all.return_value = [flow_row]

    # regressions query
    reg_qm = MagicMock()
    reg_qm.filter.return_value.filter.return_value.order_by.return_value.all.return_value = []

    call_count = [0]

    def _q(*args, **kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            return smoke_qm
        if call_count[0] == 2:
            return agg_qm
        if call_count[0] == 3:
            return flow_qm
        return reg_qm

    db.query.side_effect = _q

    result = get_eval_dashboard(current_therapist=therapist, db=db)

    # All top-level schema keys present
    assert hasattr(result, "last_smoke_test")
    assert hasattr(result, "last_30_days")
    assert hasattr(result, "by_flow_type")
    assert hasattr(result, "regressions_last_30_days")
    assert result.ai_layer_version == "phase10"
    assert result.last_smoke_test.passed is True
    assert result.last_smoke_test.run_id == 1


# ── Test 10: Health endpoint includes ai_layer block ─────────────────────────

@pytest.mark.asyncio
async def test_health_endpoint_includes_ai_layer_status():
    """GET /health returns ai_layer dict with last_smoke_test_passed field."""
    from app.main import health_check

    smoke_row = MagicMock()
    smoke_row.passed = True
    smoke_row.run_at = datetime(2026, 3, 6, 10, 0, 0)
    smoke_row.id = 7

    mock_db = MagicMock()
    query = MagicMock()
    query.filter.return_value.order_by.return_value.first.return_value = smoke_row
    mock_db.query.return_value = query

    mock_session_local = MagicMock(return_value=mock_db)

    # SessionLocal is imported inside health_check() from app.core.database
    with patch("app.core.database.SessionLocal", mock_session_local):
        response = await health_check()

    assert "ai_layer" in response
    ai_layer = response["ai_layer"]
    assert ai_layer["last_smoke_test_passed"] is True
    assert ai_layer["last_smoke_test_run_id"] == 7
    assert response["status"] == "healthy"
