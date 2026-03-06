"""DeepSummary model — Phase 8: Deep Summary longitudinal narrative."""

import enum
from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, JSON, String, Text

from app.models.base import Base


class DeepSummaryStatus(str, enum.Enum):
    DRAFT = "draft"
    APPROVED = "approved"


class DeepSummary(Base):
    """
    Full-arc clinical narrative covering an entire treatment history.

    Generated from ALL approved session summaries (oldest → newest).
    May include vault context injected into the rendering call.

    Append-only pattern: each new generation creates a new row.
    """

    __tablename__ = "deep_summaries"

    id = Column(Integer, primary_key=True, autoincrement=True)

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

    # Content
    summary_json = Column(JSON, nullable=True)          # structured extraction artifact
    rendered_text = Column(Text, nullable=True)         # Hebrew prose narrative
    sessions_covered = Column(Integer, nullable=True)   # number of approved sessions used

    # Workflow
    status = Column(String(32), nullable=False, default=DeepSummaryStatus.DRAFT.value)
    approved_at = Column(DateTime, nullable=True)

    # AI metadata
    model_used = Column(String(128), nullable=True)
    tokens_used = Column(Integer, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )
