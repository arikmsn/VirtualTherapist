"""TreatmentPlan model — Phase 7: Treatment Plan 2.0."""

import enum
from datetime import datetime

from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey,
    Integer, JSON, String, Text,
)

from app.models.base import Base


class PlanStatus(str, enum.Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class TreatmentPlan(Base):
    """
    A versioned treatment plan for a patient.

    Each update creates a new row with incremented version and parent_version_id
    pointing to the previous version. Only one row per patient can be status='active'.
    """

    __tablename__ = "treatment_plans"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Ownership
    patient_id = Column(
        Integer,
        ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    therapist_id = Column(
        Integer,
        ForeignKey("therapists.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Workflow
    status = Column(String(32), nullable=False, default=PlanStatus.ACTIVE.value)

    # Content
    plan_json = Column(JSON, nullable=True)          # structured extraction artifact
    rendered_text = Column(Text, nullable=True)      # Hebrew prose rendering

    # Versioning
    version = Column(Integer, nullable=False, default=1)
    parent_version_id = Column(
        Integer,
        ForeignKey("treatment_plans.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Drift tracking
    drift_score = Column(Float, nullable=True)       # 0.0–1.0; None = not yet checked
    drift_flags = Column(JSON, nullable=True)        # list[str] — Hebrew drift descriptions
    last_drift_check_at = Column(DateTime, nullable=True)

    # Approval
    approved_at = Column(DateTime, nullable=True)

    # Version metadata
    source = Column(String(64), nullable=True)   # "ai_generated" | "manual"
    title = Column(String(255), nullable=True)    # optional display label

    # AI metadata
    model_used = Column(String(128), nullable=True)
    tokens_used = Column(Integer, nullable=True)

    # Fingerprint caching (added migration 028)
    input_fingerprint = Column(Text, nullable=True)             # SHA-256 of inputs at generation
    input_fingerprint_version = Column(Integer, nullable=True)  # fingerprint schema version

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )
