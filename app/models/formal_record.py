"""FormalRecord model — Israeli clinical documentation."""

import enum
from datetime import datetime
from sqlalchemy import Column, String, Text, JSON, Integer, DateTime, ForeignKey
from app.models.base import Base


class RecordStatus(str, enum.Enum):
    DRAFT = "draft"
    APPROVED = "approved"
    ARCHIVED = "archived"


class FormalRecord(Base):
    """
    A formal clinical document produced for a patient's file —
    intake summaries, progress notes, termination letters, referrals, supervisor notes.

    Append-only in spirit: after approval, content should not change.
    A new record is created for each revision.
    """

    __tablename__ = "formal_records"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Context
    session_id = Column(Integer, ForeignKey("sessions.id", ondelete="SET NULL"), nullable=True)
    patient_id = Column(Integer, ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True)
    therapist_id = Column(Integer, ForeignKey("therapists.id", ondelete="CASCADE"), nullable=False, index=True)

    # Content
    record_type = Column(String(64), nullable=False)          # RecordType value
    record_json = Column(JSON, nullable=True)                 # structured extraction artifact
    rendered_text = Column(Text, nullable=True)               # final Hebrew prose

    # Workflow
    status = Column(String(32), nullable=False, default=RecordStatus.DRAFT.value)
    approved_at = Column(DateTime, nullable=True)

    # AI metadata
    model_used = Column(String(128), nullable=True)
    tokens_used = Column(Integer, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
