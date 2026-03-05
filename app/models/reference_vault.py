"""Therapist reference vault — curated internal knowledge items per therapist."""

from sqlalchemy import Column, String, Text, JSON, Boolean, Integer, ForeignKey
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class TherapistReferenceVault(BaseModel):
    """
    Internal knowledge items owned by a therapist.

    Phase 8 scope: therapist-authored content only.
    System-curated clinical theory references are deferred pending legal review.

    Items can be tagged with modality_pack_ids so the AI can surface relevant
    references during deep summary or treatment plan generation for a specific
    modality.

    source_type:
      "therapist" — created by the therapist (default)
      "system"    — reserved for future system-curated items (not seeded now)
    """

    __tablename__ = "therapist_reference_vault"

    therapist_id = Column(Integer, ForeignKey("therapists.id", ondelete="CASCADE"),
                          nullable=False, index=True)
    title = Column(String(500), nullable=False)
    content = Column(Text, nullable=False)
    tags = Column(JSON)              # list of string tags for search/display
    modality_pack_ids = Column(JSON) # list of modality_pack.id ints this item applies to
    source_type = Column(String(50), nullable=False, default="therapist")
    is_active = Column(Boolean, nullable=False, default=True)

    therapist = relationship("Therapist", foreign_keys=[therapist_id])
