"""Therapist reference vault — curated internal knowledge items per therapist."""

from sqlalchemy import Column, Float, String, Text, JSON, Boolean, Integer, ForeignKey
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class TherapistReferenceVault(BaseModel):
    """
    Internal knowledge items owned by a therapist.

    Phase 8 additions: client_id, entry_type, source_session_ids,
    embedding_vector, confidence — added in migration 021.

    source_type:
      "therapist" — created by the therapist
      "ai"        — extracted by AI from deep summary (Phase 8)
      "system"    — reserved for future system-curated items

    entry_type (Phase 8, when source_type="ai"):
      "clinical_pattern", "breakthrough", "risk_history",
      "treatment_response", "diagnostic_note"
    """

    __tablename__ = "therapist_reference_vault"

    therapist_id = Column(Integer, ForeignKey("therapists.id", ondelete="CASCADE"),
                          nullable=False, index=True)
    # nullable — cross-client insights have no client_id
    client_id = Column(Integer, ForeignKey("patients.id", ondelete="SET NULL"),
                       nullable=True, index=True)
    title = Column(String(500), nullable=True)          # nullable for AI-extracted entries
    content = Column(Text, nullable=False)
    entry_type = Column(String(64), nullable=True)      # VaultEntryType value (Phase 8)
    tags = Column(JSON)                                 # list of string tags
    source_session_ids = Column(JSON, nullable=True)    # session IDs this entry came from
    embedding_vector = Column(JSON, nullable=True)      # future use
    modality_pack_ids = Column(JSON)
    source_type = Column(String(50), nullable=False, default="therapist")
    confidence = Column(Float, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)

    therapist = relationship("Therapist", foreign_keys=[therapist_id])
