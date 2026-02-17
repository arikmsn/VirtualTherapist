"""Therapist models - stores therapist information and personalized profiles"""

from sqlalchemy import Column, String, Text, JSON, Boolean, Integer, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship
from app.models.base import BaseModel
import enum


class TherapeuticApproach(str, enum.Enum):
    """Common therapeutic approaches"""
    CBT = "CBT"  # Cognitive Behavioral Therapy
    PSYCHODYNAMIC = "psychodynamic"
    HUMANISTIC = "humanistic"
    GESTALT = "gestalt"
    DBT = "DBT"  # Dialectical Behavior Therapy
    ACT = "ACT"  # Acceptance and Commitment Therapy
    EMDR = "EMDR"
    INTEGRATIVE = "integrative"
    OTHER = "other"


class Therapist(BaseModel):
    """Therapist account and authentication"""

    __tablename__ = "therapists"

    # Basic Info
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    phone = Column(String(50))

    # Status
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)

    # Relationships
    profile = relationship(
        "TherapistProfile", back_populates="therapist",
        uselist=False, cascade="all, delete-orphan",
    )
    patients = relationship("Patient", back_populates="therapist", cascade="all, delete-orphan")
    sessions = relationship("Session", back_populates="therapist", cascade="all, delete-orphan")
    messages = relationship("Message", back_populates="therapist", cascade="all, delete-orphan")


class TherapistProfile(BaseModel):
    """
    Personalized therapist profile - the AI learns this to mimic the therapist's style
    This is the CORE of personalization!
    """

    __tablename__ = "therapist_profiles"

    therapist_id = Column(Integer, ForeignKey("therapists.id"), unique=True, nullable=False)

    # Therapeutic Approach
    therapeutic_approach = Column(SQLEnum(TherapeuticApproach), nullable=False)
    approach_description = Column(Text)  # Detailed description

    # Writing Style (AI learns this!)
    tone = Column(String(100))  # e.g., "supportive, direct", "gentle, empathetic"
    message_length_preference = Column(String(50))  # "short", "medium", "detailed"
    common_terminology = Column(JSON)  # List of preferred terms

    # Session Summary Style
    summary_template = Column(Text)  # Custom template for summaries
    # Preferred sections: ["topics", "interventions", "progress", "next_steps"]
    summary_sections = Column(JSON)

    # Communication Preferences
    follow_up_frequency = Column(String(50))  # "daily", "weekly", "as_needed"
    preferred_exercises = Column(JSON)  # Common exercises this therapist uses

    # Language & Culture
    language = Column(String(10), default="he")  # Hebrew by default
    cultural_considerations = Column(Text)

    # AI Learning Data
    # Examples of therapist's previous summaries for AI to learn from
    example_summaries = Column(JSON)
    example_messages = Column(JSON)  # Examples of messages to patients

    # Onboarding Status
    onboarding_completed = Column(Boolean, default=False)
    onboarding_step = Column(Integer, default=0)

    # Relationship
    therapist = relationship("Therapist", back_populates="profile")
