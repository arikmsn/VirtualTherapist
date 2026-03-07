"""AudioClip model — individual recording segments within a session.

Each session can have multiple clips recorded sequentially.
Each clip is transcribed immediately on upload; the final summary
is generated from the merged transcript of all clips.
"""

from sqlalchemy import Column, Integer, String, Text, ForeignKey
from app.models.base import BaseModel


class AudioClip(BaseModel):
    """A single audio recording clip belonging to a session."""

    __tablename__ = "audio_clips"

    session_id = Column(Integer, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False)
    therapist_id = Column(Integer, ForeignKey("therapists.id", ondelete="CASCADE"), nullable=False)

    # 1-based index within the session (clip 1, clip 2, …)
    clip_index = Column(Integer, nullable=False)

    # Duration in seconds (recorded by the browser; -1 if unknown)
    duration_seconds = Column(Integer, nullable=True)

    # Whisper transcript — null until transcription completes
    transcript = Column(Text, nullable=True)

    # pending | transcribed | error
    status = Column(String(20), nullable=False, default="pending")
    error_message = Column(Text, nullable=True)
