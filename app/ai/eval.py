"""Phase 10 — In-house AI Evaluation Framework.

No external eval framework. Uses data already in the DB (approved summaries,
completeness scores, ai_generation_log) to measure output quality and detect
regressions when prompts or models change.

EvalRunType hierarchy:
  smoke_test  — 5 samples, runs on every deploy, blocks health-check if failed
  regression  — compares current metrics to last passing baseline
  full_audit  — all approved summaries, intended for weekly scheduled run
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional

from loguru import logger
from sqlalchemy.orm import Session as DBSession

from app.ai.models import FlowType


# ── Enums & config ────────────────────────────────────────────────────────────

class EvalRunType(str, Enum):
    SMOKE_TEST = "smoke_test"
    REGRESSION = "regression"
    FULL_AUDIT = "full_audit"


@dataclass
class EvalConfig:
    run_type: EvalRunType
    flow_type: FlowType
    sample_size: int
    min_completeness_threshold: float = 0.6
    min_confidence_threshold: float = 0.7
    max_regression_delta: float = 0.1   # mean drop > 0.1 vs baseline → flag


@dataclass
class SampleResult:
    session_id: Optional[int]
    flow_type: str
    input_hash: str
    output_text: str
    completeness_score: Optional[float]
    confidence: Optional[float]
    edit_distance: Optional[int]
    passed: bool
    failure_reason: Optional[str]


@dataclass
class EvalRunResult:
    run_id: int
    run_type: EvalRunType
    passed: bool
    mean_completeness: float
    mean_confidence: float
    mean_edit_distance: float
    regression_detected: bool
    regression_details: dict
    sample_size: int
    duration_ms: int


# ── Helpers ───────────────────────────────────────────────────────────────────

def _hash_input(text: str) -> str:
    """SHA-256 of input string — used to track if same input was re-evaluated."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:64]


def _safe_mean(values: list) -> float:
    clean = [v for v in values if v is not None]
    return sum(clean) / len(clean) if clean else 0.0


# ── Core evaluator ────────────────────────────────────────────────────────────

class AIEvaluator:
    """
    In-house AI quality evaluator.

    Reads approved SessionSummary rows (the ground-truth source) and scores
    quality using the metrics already stored: completeness_score, ai_confidence,
    and therapist_edit_distance.

    Important: the smoke test and regression runs do NOT re-call the LLM — they
    use the stored metrics from real past generations.  This keeps smoke tests
    fast (< 1 s) and deterministic — no token spend, no flakiness.
    """

    def __init__(self, db: DBSession) -> None:
        self.db = db

    # ── Public API ────────────────────────────────────────────────────────────

    async def run_smoke_test(self) -> EvalRunResult:
        """Fast: last 5 approved summaries with completeness data."""
        config = EvalConfig(
            run_type=EvalRunType.SMOKE_TEST,
            flow_type=FlowType.SESSION_SUMMARY,
            sample_size=5,
            min_completeness_threshold=0.6,
            min_confidence_threshold=0.7,
        )
        return await self.run_eval(config, triggered_by="deploy")

    async def run_eval(
        self,
        config: EvalConfig,
        triggered_by: str = "manual",
    ) -> EvalRunResult:
        """Run an evaluation batch using stored metrics — no LLM calls."""
        from app.models.session import SessionSummary
        from app.models.session import Session as SessionModel
        from app.models.eval import AIEvalRun, AIEvalSample

        t_start = time.monotonic()

        # ── Fetch samples ─────────────────────────────────────────────────────
        query = (
            self.db.query(SessionSummary)
            .filter(
                SessionSummary.approved_by_therapist == True,  # noqa: E712
                SessionSummary.completeness_score.isnot(None),
            )
            .order_by(SessionSummary.id.desc())
            .limit(config.sample_size)
        )
        summaries = query.all()

        samples: list[SampleResult] = []
        for s in summaries:
            input_text = s.ai_draft_text or s.full_summary or ""
            score = s.completeness_score or 0.0
            conf = (s.ai_confidence or 0) / 100.0   # stored 0-100, normalise to 0-1
            edit_dist = s.therapist_edit_distance

            failures = []
            if score < config.min_completeness_threshold:
                failures.append(
                    f"completeness {score:.2f} < {config.min_completeness_threshold}"
                )
            if conf < config.min_confidence_threshold:
                failures.append(
                    f"confidence {conf:.2f} < {config.min_confidence_threshold}"
                )

            # Retrieve session_id from the session relationship
            session_id = None
            try:
                session_id = s.session.id if s.session else None
            except Exception:
                pass

            samples.append(SampleResult(
                session_id=session_id,
                flow_type=config.flow_type.value,
                input_hash=_hash_input(input_text[:500]),
                output_text=(s.full_summary or "")[:500],
                completeness_score=score,
                confidence=conf,
                edit_distance=edit_dist,
                passed=len(failures) == 0,
                failure_reason="; ".join(failures) if failures else None,
            ))

        # ── Aggregate metrics ─────────────────────────────────────────────────
        mean_comp = _safe_mean([s.completeness_score for s in samples])
        mean_conf = _safe_mean([s.confidence for s in samples])
        mean_edit = _safe_mean([s.edit_distance for s in samples])
        overall_passed = all(s.passed for s in samples) if samples else False

        # ── Regression check ──────────────────────────────────────────────────
        regression_detected = False
        regression_details: dict = {}
        if config.run_type == EvalRunType.REGRESSION:
            baseline = await self.get_baseline(config.flow_type)
            if baseline:
                reg = self.compare_to_baseline(
                    mean_comp, mean_conf, baseline, config.max_regression_delta
                )
                regression_detected = reg["regression_detected"]
                regression_details = reg

        # ── Persist eval run ──────────────────────────────────────────────────
        duration_ms = int((time.monotonic() - t_start) * 1000)
        run_row = AIEvalRun(
            run_type=config.run_type.value,
            flow_type=config.flow_type.value,
            triggered_by=triggered_by,
            model_used=None,           # stored metrics; no specific model call
            sample_size=len(samples),
            mean_completeness=mean_comp,
            mean_confidence=mean_conf,
            mean_edit_distance=mean_edit if mean_edit else None,
            regression_detected=regression_detected,
            regression_details=regression_details or None,
            passed=overall_passed,
            run_at=datetime.utcnow(),
            duration_ms=duration_ms,
        )
        self.db.add(run_row)
        self.db.flush()   # populate run_row.id

        for sample in samples:
            self.db.add(AIEvalSample(
                eval_run_id=run_row.id,
                session_id=sample.session_id,
                flow_type=sample.flow_type,
                input_hash=sample.input_hash,
                output_text=sample.output_text,
                completeness_score=sample.completeness_score,
                confidence=sample.confidence,
                edit_distance=sample.edit_distance,
                passed=sample.passed,
                failure_reason=sample.failure_reason,
            ))

        self.db.commit()

        logger.info(
            f"[Eval] {config.run_type.value} run_id={run_row.id} "
            f"samples={len(samples)} passed={overall_passed} "
            f"comp={mean_comp:.2f} conf={mean_conf:.2f} "
            f"regression={regression_detected}"
        )

        return EvalRunResult(
            run_id=run_row.id,
            run_type=config.run_type,
            passed=overall_passed,
            mean_completeness=mean_comp,
            mean_confidence=mean_conf,
            mean_edit_distance=mean_edit,
            regression_detected=regression_detected,
            regression_details=regression_details,
            sample_size=len(samples),
            duration_ms=duration_ms,
        )

    async def get_baseline(self, flow_type: FlowType) -> Optional[dict]:
        """
        Return the most recent passed=True eval run metrics for this flow_type.

        Returns None if no baseline exists yet (first run ever).
        """
        from app.models.eval import AIEvalRun

        baseline_row = (
            self.db.query(AIEvalRun)
            .filter(
                AIEvalRun.flow_type == flow_type.value,
                AIEvalRun.passed == True,       # noqa: E712
            )
            .order_by(AIEvalRun.run_at.desc())
            .first()
        )
        if not baseline_row:
            return None
        return {
            "mean_completeness": baseline_row.mean_completeness,
            "mean_confidence": baseline_row.mean_confidence,
            "run_id": baseline_row.id,
            "run_at": baseline_row.run_at.isoformat() if baseline_row.run_at else None,
        }

    @staticmethod
    def compare_to_baseline(
        current_comp: float,
        current_conf: float,
        baseline: dict,
        max_delta: float,
    ) -> dict:
        """
        Compare current metrics to baseline.

        Returns a dict with regression_detected bool and per-metric details.
        """
        results: dict = {"regression_detected": False, "metrics": []}

        baseline_comp = baseline.get("mean_completeness") or 0.0
        baseline_conf = baseline.get("mean_confidence") or 0.0

        comp_delta = current_comp - baseline_comp
        conf_delta = current_conf - baseline_conf

        if comp_delta < -max_delta:
            results["regression_detected"] = True
            results["metrics"].append({
                "metric": "completeness",
                "baseline": baseline_comp,
                "current": current_comp,
                "delta": round(comp_delta, 4),
            })

        if conf_delta < -max_delta:
            results["regression_detected"] = True
            results["metrics"].append({
                "metric": "confidence",
                "baseline": baseline_conf,
                "current": current_conf,
                "delta": round(conf_delta, 4),
            })

        return results
