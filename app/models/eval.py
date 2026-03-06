"""ORM models for Phase 10 Evaluation Framework."""

from datetime import datetime

from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey,
    Integer, JSON, String, Text,
)

from app.models.base import Base


class AIEvalRun(Base):
    """
    One evaluation run — stores aggregate metrics for a batch of samples.

    Triggered by: deploy (smoke_test), scheduled job (full_audit), or manual API call.
    """

    __tablename__ = "ai_eval_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)

    run_type = Column(String(64), nullable=True)          # EvalRunType value
    flow_type = Column(String(64), nullable=True)          # FlowType value (or None = all)
    triggered_by = Column(String(32), nullable=True)       # 'manual' | 'scheduled' | 'deploy'
    model_used = Column(String(128), nullable=True)

    # Aggregate quality metrics
    sample_size = Column(Integer, nullable=True)
    mean_completeness = Column(Float, nullable=True)
    mean_confidence = Column(Float, nullable=True)
    mean_edit_distance = Column(Float, nullable=True)
    mean_therapist_rating = Column(Float, nullable=True)   # nullable — not always rated

    # Regression tracking
    regression_detected = Column(Boolean, default=False, nullable=True)
    regression_details = Column(JSON, nullable=True)

    # Outcome
    passed = Column(Boolean, nullable=True)

    # Timing
    run_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    duration_ms = Column(Integer, nullable=True)


class AIEvalSample(Base):
    """One per-sample result row within an eval run."""

    __tablename__ = "ai_eval_samples"

    id = Column(Integer, primary_key=True, autoincrement=True)

    eval_run_id = Column(Integer, ForeignKey("ai_eval_runs.id", ondelete="CASCADE"),
                         nullable=True)
    session_id = Column(Integer, nullable=True)
    flow_type = Column(String(64), nullable=True)
    input_hash = Column(String(64), nullable=True)     # SHA256 of input (for dedup / replay)
    output_text = Column(Text, nullable=True)

    # Quality signals
    completeness_score = Column(Float, nullable=True)
    confidence = Column(Float, nullable=True)
    edit_distance = Column(Integer, nullable=True)     # vs therapist-approved text

    # Outcome
    passed = Column(Boolean, nullable=True)
    failure_reason = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
