"""AI generation log — append-only telemetry for every AI call."""

from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, ForeignKey, DateTime
from sqlalchemy.ext.declarative import declarative_base
from app.models.base import Base


class AIGenerationLog(Base):
    """
    Append-only row written for every call to the AIProvider.

    Used for:
    - Cost/latency tracking by route and model
    - Confidence calibration quality assessment
    - Edit-distance capture (filled post-approval by the summary service)
    - Evaluation framework data collection (Phase 10)

    Note: inherits Base directly (not BaseModel) because this table is
    append-only and has no updated_at column.
    """

    __tablename__ = "ai_generation_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Context
    therapist_id = Column(Integer, ForeignKey("therapists.id", ondelete="SET NULL"),
                          nullable=True, index=True)
    flow_type = Column(String(100), nullable=False, index=True)
    session_summary_id = Column(Integer,
                                ForeignKey("session_summaries.id", ondelete="SET NULL"),
                                nullable=True)
    session_id = Column(Integer, ForeignKey("sessions.id", ondelete="SET NULL"),
                        nullable=True)
    modality_pack_id = Column(Integer,
                              ForeignKey("modality_packs.id", ondelete="SET NULL"),
                              nullable=True)

    # Routing
    model_used = Column(String(200), nullable=False)
    route_reason = Column(String(500))    # e.g. "flow:session_summary" or "deep_mode"
    prompt_version = Column(String(50))

    # Quality signals
    ai_confidence = Column(Float)
    completeness_score = Column(Float)
    # Levenshtein distance between ai_draft_text and therapist-approved text;
    # written by session_service.approve_summary() — NULL until approved.
    therapist_edit_distance = Column(Integer)

    # Performance
    prompt_tokens = Column(Integer)
    completion_tokens = Column(Integer)
    generation_ms = Column(Integer)
