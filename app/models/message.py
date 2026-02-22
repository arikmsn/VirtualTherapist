"""Message models - messages between therapist AI and patients"""

from sqlalchemy import Column, String, Text, Boolean, Integer, ForeignKey, DateTime, Enum as SQLEnum
from sqlalchemy.orm import relationship
from app.models.base import BaseModel
import enum


class MessageStatus(str, enum.Enum):
    """Message approval and delivery status"""
    DRAFT = "draft"  # AI created, awaiting therapist review
    PENDING_APPROVAL = "pending_approval"  # Waiting for therapist approval
    APPROVED = "approved"  # Therapist approved, ready to send
    SCHEDULED = "scheduled"  # Approved + scheduled for future delivery
    SENT = "sent"  # Sent to patient via channel
    DELIVERED = "delivered"  # Delivered confirmation from channel
    READ = "read"  # Patient read the message
    REPLIED = "replied"  # Patient replied
    REJECTED = "rejected"  # Therapist rejected the message
    CANCELLED = "cancelled"  # Therapist cancelled a scheduled message
    FAILED = "failed"  # Delivery attempt failed (channel error)


class MessageDirection(str, enum.Enum):
    """Message direction"""
    TO_PATIENT = "to_patient"  # From therapist (AI) to patient
    FROM_PATIENT = "from_patient"  # From patient to therapist


class Message(BaseModel):
    """
    Messages sent to patients (in therapist's name!)
    CRITICAL: Every message MUST be approved by therapist before sending
    """

    __tablename__ = "messages"

    therapist_id = Column(Integer, ForeignKey("therapists.id"), nullable=False)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)

    # Message Content
    direction = Column(SQLEnum(MessageDirection, native_enum=False), nullable=False)
    content = Column(Text, nullable=False)  # The actual message text

    # Status & Approval
    status = Column(SQLEnum(MessageStatus, native_enum=False), default=MessageStatus.DRAFT)

    # Approval Tracking (CRITICAL for ethics!)
    requires_approval = Column(Boolean, default=True)
    approved_at = Column(DateTime)
    rejected_at = Column(DateTime)
    rejection_reason = Column(Text)

    # Delivery Tracking
    sent_at = Column(DateTime)
    delivered_at = Column(DateTime)
    read_at = Column(DateTime)

    # Message Metadata
    message_type = Column(String(50))  # "follow_up", "exercise_reminder", "check_in", "response"
    related_session_id = Column(Integer, ForeignKey("sessions.id"))
    related_exercise = Column(String(255))  # If about a specific exercise

    # AI Generation Info
    generated_by_ai = Column(Boolean, default=True)
    ai_prompt_used = Column(Text)  # The prompt used to generate this message
    ai_model = Column(String(100))  # Model that generated it

    # Scheduling & Channel (Messages Center v1)
    scheduled_send_at = Column(DateTime)  # If set + status=SCHEDULED, APScheduler sends at this time
    channel = Column(String(50), default="whatsapp")  # "whatsapp" (extensible to sms, email)
    recipient_phone = Column(String(100))  # Final send-to number; may differ from patient default

    # Patient Response
    patient_response = Column(Text)  # If patient replied (future: two-way flow)
    response_received_at = Column(DateTime)

    # Relationships
    therapist = relationship("Therapist", back_populates="messages")
    patient = relationship("Patient", back_populates="messages")
