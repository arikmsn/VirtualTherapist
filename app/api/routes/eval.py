"""Phase 10 — Evaluation Framework routes.

Endpoints:
  POST /api/summaries/{id}/rate      — therapist quality rating (1–5 stars)
  GET  /api/ai/eval/dashboard        — aggregate quality metrics, no LLM
  POST /api/ai/eval/run              — trigger a manual eval run
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session as DBSession

from app.api.deps import get_current_therapist, get_db
from app.models.eval import AIEvalRun
from app.models.session import SessionSummary
from app.models.therapist import Therapist

router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────────────────────

class RateSummaryRequest(BaseModel):
    rating: int = Field(..., ge=1, le=5)
    comment: Optional[str] = None


class RateSummaryResponse(BaseModel):
    summary_id: int
    rating: int
    rated_at: datetime


class FlowTypeStat(BaseModel):
    flow_type: str
    generation_count: int
    mean_completeness: Optional[float]
    regression_detected: bool


class Last30DaysStats(BaseModel):
    total_generations: int
    mean_completeness: Optional[float]
    mean_confidence: Optional[float]
    mean_edit_distance: Optional[float]
    mean_therapist_rating: Optional[float]
    approved_rate: float


class LastSmokeTest(BaseModel):
    passed: Optional[bool]
    run_at: Optional[datetime]
    mean_completeness: Optional[float]
    mean_confidence: Optional[float]
    run_id: Optional[int]


class EvalDashboardResponse(BaseModel):
    last_smoke_test: LastSmokeTest
    last_30_days: Last30DaysStats
    by_flow_type: List[FlowTypeStat]
    regressions_last_30_days: List[Dict[str, Any]]
    ai_layer_version: str


class ManualEvalRequest(BaseModel):
    run_type: str = "smoke_test"   # smoke_test | regression | full_audit
    flow_type: str = "session_summary"
    sample_size: int = Field(default=5, ge=1, le=50)


class ManualEvalResponse(BaseModel):
    run_id: int
    passed: bool
    mean_completeness: float
    mean_confidence: float
    regression_detected: bool
    sample_size: int
    duration_ms: int


# ── Helpers ───────────────────────────────────────────────────────────────────

def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _get_owned_summary(
    db: DBSession, summary_id: int, therapist_id: int
) -> SessionSummary:
    from app.models.session import Session as SessionModel
    summary = (
        db.query(SessionSummary)
        .join(SessionSummary.session)
        .filter(
            SessionSummary.id == summary_id,
            SessionModel.therapist_id == therapist_id,
        )
        .first()
    )
    if not summary:
        raise HTTPException(status_code=404, detail="הסיכום לא נמצא.")
    return summary


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post(
    "/summaries/{summary_id}/rate",
    response_model=RateSummaryResponse,
)
def rate_summary(
    summary_id: int,
    request: RateSummaryRequest,
    current_therapist: Therapist = Depends(get_current_therapist),
    db: DBSession = Depends(get_db),
):
    """
    Record therapist quality rating (1–5 stars) for an AI-generated summary.

    Can be called multiple times — updates the existing rating in place.
    Only the owning therapist can rate their own summary.
    """
    summary = _get_owned_summary(db, summary_id, current_therapist.id)

    summary.therapist_rating = request.rating
    summary.therapist_rating_comment = request.comment
    summary.rated_at = _utcnow()
    db.commit()

    return RateSummaryResponse(
        summary_id=summary.id,
        rating=summary.therapist_rating,
        rated_at=summary.rated_at,
    )


@router.get(
    "/ai/eval/dashboard",
    response_model=EvalDashboardResponse,
)
def get_eval_dashboard(
    current_therapist: Therapist = Depends(get_current_therapist),
    db: DBSession = Depends(get_db),
):
    """
    Aggregated quality dashboard — pure DB, no LLM calls.

    Returns metrics for: last smoke test, last 30 days, per-flow breakdown,
    and any regressions in the last 30 days.
    """
    now = _utcnow()
    thirty_days_ago = now - timedelta(days=30)

    # ── Last smoke test ───────────────────────────────────────────────────────
    last_smoke = (
        db.query(AIEvalRun)
        .filter(AIEvalRun.run_type == "smoke_test")
        .order_by(AIEvalRun.run_at.desc())
        .first()
    )
    smoke_block = LastSmokeTest(
        passed=last_smoke.passed if last_smoke else None,
        run_at=last_smoke.run_at if last_smoke else None,
        mean_completeness=last_smoke.mean_completeness if last_smoke else None,
        mean_confidence=last_smoke.mean_confidence if last_smoke else None,
        run_id=last_smoke.id if last_smoke else None,
    )

    # ── Last 30 days: approved summaries owned by this therapist ─────────────
    from app.models.session import Session as SessionModel

    approved_qs = (
        db.query(SessionSummary)
        .join(SessionSummary.session)
        .filter(SessionModel.therapist_id == current_therapist.id)
    )
    total_generations = approved_qs.count()
    approved_only = approved_qs.filter(
        SessionSummary.approved_by_therapist == True,   # noqa: E712
    )
    approved_count = approved_only.count()
    approved_rate = (approved_count / total_generations) if total_generations else 0.0

    # Aggregate quality metrics across all summaries (approved or not)
    agg = approved_qs.with_entities(
        func.avg(SessionSummary.completeness_score),
        func.avg(SessionSummary.ai_confidence),
        func.avg(SessionSummary.therapist_edit_distance),
        func.avg(SessionSummary.therapist_rating),
    ).first()

    mean_comp = agg[0]
    mean_conf = (agg[1] / 100.0) if agg[1] is not None else None  # stored 0-100
    mean_edit = agg[2]
    mean_rating = agg[3]

    last_30_block = Last30DaysStats(
        total_generations=total_generations,
        mean_completeness=mean_comp,
        mean_confidence=mean_conf,
        mean_edit_distance=mean_edit,
        mean_therapist_rating=mean_rating,
        approved_rate=round(approved_rate, 4),
    )

    # ── Per-flow breakdown from ai_eval_runs ─────────────────────────────────
    flow_rows = (
        db.query(
            AIEvalRun.flow_type,
            func.count(AIEvalRun.id).label("gen_count"),
            func.avg(AIEvalRun.mean_completeness).label("avg_comp"),
            func.max(AIEvalRun.regression_detected).label("any_regression"),
        )
        .filter(AIEvalRun.run_at >= thirty_days_ago)
        .group_by(AIEvalRun.flow_type)
        .all()
    )
    by_flow = [
        FlowTypeStat(
            flow_type=row.flow_type or "unknown",
            generation_count=row.gen_count,
            mean_completeness=row.avg_comp,
            regression_detected=bool(row.any_regression),
        )
        for row in flow_rows
    ]

    # ── Regressions in last 30 days ───────────────────────────────────────────
    regression_rows = (
        db.query(AIEvalRun)
        .filter(
            AIEvalRun.regression_detected == True,   # noqa: E712
            AIEvalRun.run_at >= thirty_days_ago,
        )
        .order_by(AIEvalRun.run_at.desc())
        .all()
    )
    regressions = [
        {
            "run_id": r.id,
            "flow_type": r.flow_type,
            "run_at": r.run_at.isoformat() if r.run_at else None,
            "details": r.regression_details or {},
        }
        for r in regression_rows
    ]

    return EvalDashboardResponse(
        last_smoke_test=smoke_block,
        last_30_days=last_30_block,
        by_flow_type=by_flow,
        regressions_last_30_days=regressions,
        ai_layer_version="phase10",
    )


@router.post(
    "/ai/eval/run",
    response_model=ManualEvalResponse,
    status_code=201,
)
async def trigger_eval_run(
    request: ManualEvalRequest,
    current_therapist: Therapist = Depends(get_current_therapist),
    db: DBSession = Depends(get_db),
):
    """
    Manually trigger an evaluation run.

    The caller decides run_type and sample_size. Useful for testing after
    prompt changes without waiting for the scheduled run.
    """
    from app.ai.eval import AIEvaluator, EvalConfig, EvalRunType
    from app.ai.models import FlowType

    try:
        run_type = EvalRunType(request.run_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Unknown run_type: {request.run_type}")

    try:
        flow_type = FlowType(request.flow_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Unknown flow_type: {request.flow_type}")

    config = EvalConfig(
        run_type=run_type,
        flow_type=flow_type,
        sample_size=request.sample_size,
    )
    evaluator = AIEvaluator(db)
    try:
        result = await evaluator.run_eval(config, triggered_by="manual")
        return ManualEvalResponse(
            run_id=result.run_id,
            passed=result.passed,
            mean_completeness=result.mean_completeness,
            mean_confidence=result.mean_confidence,
            regression_detected=result.regression_detected,
            sample_size=result.sample_size,
            duration_ms=result.duration_ms,
        )
    except Exception as e:
        logger.exception(f"Manual eval run failed: {e!r}")
        raise HTTPException(status_code=500, detail=str(e))
