"""Therapist signature profile — learned style model built from approved summaries."""

from sqlalchemy import Column, String, Text, JSON, Boolean, Integer, Float, ForeignKey
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class TherapistSignatureProfile(BaseModel):
    """
    Inferred representation of a therapist's clinical style.

    Built exclusively from therapist-approved (and optionally edited) session
    summaries, treatment plans, and other therapist-authored artifacts.
    Raw AI drafts that were never approved do NOT influence this profile.

    Each meaningful style change bumps the version so the history is preserved.
    The profile with is_active=True is the current version used for generation.

    Style dimensions use a 0.0–1.0 float scale where the two extremes are
    labelled in the column comments below.  NULL means "not yet inferred"
    (insufficient data).

    Minimum data threshold: meaningful personalization activates after 5+
    approved summaries (approved_summary_count >= 5). Below that threshold,
    generation falls back to the modality pack defaults.
    """

    __tablename__ = "therapist_signature_profiles"

    therapist_id = Column(Integer, ForeignKey("therapists.id", ondelete="CASCADE"),
                          nullable=False, index=True)
    version = Column(Integer, nullable=False, default=1)

    # ── Style dimensions (0.0 → 1.0) ─────────────────────────────────────────
    concise_vs_detailed = Column(Float)          # 0=concise, 1=detailed
    directive_vs_exploratory = Column(Float)     # 0=directive, 1=exploratory
    emotional_vs_cognitive_emphasis = Column(Float)  # 0=emotional, 1=cognitive
    homework_task_orientation = Column(Float)    # 0=low, 1=high
    structure_preference = Column(String(50))    # "bullets" | "narrative" | "mixed"
    preferred_intervention_naming = Column(JSON) # list of verbatim terms used
    documentation_rigor = Column(Float)          # 0=minimal, 1=thorough
    risk_followup_inclusion = Column(Float)      # 0=rarely, 1=always
    measurable_goals_tendency = Column(Float)    # 0=qualitative, 1=measurable
    preferred_tone = Column(String(100))         # "formal" | "warm" | "direct" | "exploratory"
    conceptual_evidence_orientation = Column(Float)  # 0=none, 1=strong theory/research refs
    hebrew_english_mix = Column(Float)           # 0=Hebrew only, 1=heavy English mix
    preferred_terminology = Column(JSON)         # {term: frequency} from approved summaries

    # ── Metadata ──────────────────────────────────────────────────────────────
    # Per-dimension confidence 0–1 (low confidence = more approved summaries needed)
    confidence_scores = Column(JSON)
    # Non-PHI phrase samples used to infer each dimension (for explainability UI)
    evidence_snippets = Column(JSON)
    # How many approved summaries this version is based on
    approved_summary_count = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, nullable=False, default=True)

    # ── Relationships ─────────────────────────────────────────────────────────
    therapist = relationship("Therapist", foreign_keys=[therapist_id])
