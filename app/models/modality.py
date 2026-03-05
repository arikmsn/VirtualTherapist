"""Modality pack model — versioned clinical framing definitions per therapeutic approach."""

from sqlalchemy import Column, String, Text, JSON, Boolean, Integer
from app.models.base import BaseModel


class ModalityPack(BaseModel):
    """
    Versioned definition of a therapeutic modality (CBT, DBT, ACT, etc.).

    Each pack carries:
    - A prompt_module: the clinical framing text injected into AI generation prompts.
    - Structured completeness requirements (required / recommended summary fields).
    - Terminology preferences for natural Hebrew output.

    Packs are seeded by migration 014. Admin editing and DB-backed versioning
    are deferred to a later phase; for now the version field tracks manual bumps.
    """

    __tablename__ = "modality_packs"

    name = Column(String(100), unique=True, nullable=False)   # e.g. "cbt", "generic_integrative"
    label = Column(String(200), nullable=False)               # English display label
    label_he = Column(String(200))                            # Hebrew display label
    description = Column(Text)
    prompt_module = Column(Text)                              # Clinical framing injected into prompts

    # Completeness-checker configuration (list of field names)
    required_summary_fields = Column(JSON)
    recommended_summary_fields = Column(JSON)

    # Terminology guidance for Hebrew output generation
    preferred_terminology = Column(JSON)   # {en_term: he_translation}
    evidence_tags = Column(JSON)           # list of tags for routing/display
    output_style_hints = Column(Text)

    version = Column(Integer, nullable=False, default=1)
    is_active = Column(Boolean, nullable=False, default=True)
