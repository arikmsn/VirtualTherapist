"""Audit log model - tracks all system actions for security and compliance"""

from sqlalchemy import Column, String, Text, Integer, JSON, DateTime
from app.models.base import BaseModel
from datetime import datetime
import enum


class AuditLog(BaseModel):
    """
    Complete audit trail of all actions
    CRITICAL for GDPR compliance and security
    """

    __tablename__ = "audit_logs"

    # Who
    user_id = Column(Integer)  # Therapist ID
    user_type = Column(String(50))  # "therapist", "patient", "system", "admin"
    user_email = Column(String(255))

    # What
    action = Column(String(100), nullable=False)  # "create", "read", "update", "delete", "approve", "send"
    resource_type = Column(String(100), nullable=False)  # "patient", "message", "session", "summary"
    resource_id = Column(Integer)

    # When
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Where
    ip_address = Column(String(50))
    user_agent = Column(String(500))

    # Details
    action_details = Column(JSON)  # Full details of the action
    old_value = Column(Text)  # Previous value (for updates)
    new_value = Column(Text)  # New value (for updates)

    # Security
    success = Column(Boolean, default=True)
    error_message = Column(Text)  # If action failed

    # GDPR
    gdpr_relevant = Column(Boolean, default=False)  # If this action involves personal data
    data_category = Column(String(100))  # "personal", "medical", "contact", etc.
