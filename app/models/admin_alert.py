"""AdminAlert model — stores system alerts for the admin panel."""

from sqlalchemy import Column, String, Text, Boolean, Integer, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.base import BaseModel


class AdminAlert(BaseModel):
    """System alerts: new signups, AI errors, blocked attempts, etc."""

    __tablename__ = "admin_alerts"

    # Suppress the inherited updated_at column — admin_alerts table was created without it
    updated_at = None  # type: ignore[assignment]

    type = Column(String(64), nullable=False)   # "new_signup", "ai_error", "blocked_login"
    message = Column(Text, nullable=False)
    therapist_id = Column(Integer, ForeignKey("therapists.id", ondelete="SET NULL"), nullable=True)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    therapist = relationship("Therapist", foreign_keys=[therapist_id])
