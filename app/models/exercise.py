"""Exercise / homework tracking model."""

from datetime import datetime
from sqlalchemy import Column, Integer, Text, Boolean, DateTime, ForeignKey
from app.models.base import BaseModel


class Exercise(BaseModel):
    """
    Individual exercise or homework item assigned to a patient.
    Linked optionally to the session summary it was assigned in.
    """
    __tablename__ = "exercises"

    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False, index=True)
    therapist_id = Column(Integer, ForeignKey("therapists.id"), nullable=False)
    session_summary_id = Column(Integer, ForeignKey("session_summaries.id"), nullable=True)

    description = Column(Text, nullable=False)
    completed = Column(Boolean, default=False, nullable=False)
    completed_at = Column(DateTime, nullable=True)
