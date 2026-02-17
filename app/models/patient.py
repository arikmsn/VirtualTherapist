"""Patient models - stores patient information and status"""

from sqlalchemy import (
    Column, String, Text, JSON, Boolean, Integer,
    ForeignKey, Enum as SQLEnum, Date,
)
from sqlalchemy.orm import relationship
from app.models.base import BaseModel
import enum


class PatientStatus(str, enum.Enum):
    """Patient treatment status"""
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    INACTIVE = "inactive"


class Patient(BaseModel):
    """Patient information (encrypted for privacy)"""

    __tablename__ = "patients"

    therapist_id = Column(Integer, ForeignKey("therapists.id"), nullable=False)

    # Basic Info (will be encrypted)
    full_name_encrypted = Column(Text, nullable=False)  # Encrypted
    phone_encrypted = Column(Text)  # Encrypted
    email_encrypted = Column(Text)  # Encrypted

    # Treatment Info
    status = Column(SQLEnum(PatientStatus), default=PatientStatus.ACTIVE)
    start_date = Column(Date)

    # Clinical Notes (encrypted)
    primary_concerns = Column(Text)  # Encrypted - main issues being addressed
    diagnosis = Column(Text)  # Encrypted - clinical diagnosis if any
    treatment_goals = Column(JSON)  # Encrypted - list of treatment goals

    # Current Status
    current_exercises = Column(JSON)  # Active homework/exercises
    last_contact_date = Column(Date)
    next_session_date = Column(Date)

    # Follow-up Tracking
    pending_followups = Column(JSON)  # List of pending follow-ups
    completed_exercises_count = Column(Integer, default=0)
    missed_exercises_count = Column(Integer, default=0)

    # AI Interaction Settings
    allow_ai_contact = Column(Boolean, default=True)  # Patient consent for AI messages
    preferred_contact_time = Column(String(50))  # "morning", "afternoon", "evening"

    # Relationships
    therapist = relationship("Therapist", back_populates="patients")
    sessions = relationship("Session", back_populates="patient", cascade="all, delete-orphan")
    messages = relationship("Message", back_populates="patient", cascade="all, delete-orphan")
