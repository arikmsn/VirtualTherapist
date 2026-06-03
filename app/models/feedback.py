"""FeedbackMessage — in-app bug reports and contact messages."""

from sqlalchemy import Column, Integer, String, Text, ForeignKey
from app.models.base import BaseModel


class FeedbackMessage(BaseModel):
    """
    Stores every in-app 'Report a bug / Contact us' submission.
    DB save is the source of truth; email delivery is best-effort.
    """

    __tablename__ = "feedback_messages"

    therapist_id = Column(
        Integer,
        ForeignKey("therapists.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    therapist_name = Column(String(255), nullable=False)
    therapist_email = Column(String(255), nullable=False)

    type = Column(String(20), nullable=False)           # 'bug' | 'contact'
    subject = Column(String(255), nullable=True)
    message = Column(Text, nullable=False)

    # Workflow state — reserved for future admin triage
    status = Column(String(20), nullable=False, default="new", server_default="new")

    # Email delivery tracking (best-effort — never blocks submission)
    email_delivery_status = Column(
        String(20), nullable=False, default="pending", server_default="pending"
    )  # 'pending' | 'sent' | 'failed' | 'skipped'
    email_delivery_error = Column(Text, nullable=True)
