"""
TherapistStyleProfile — merged view of TherapistProfile + TherapistSignatureProfile.

Implements spec section §3.1 of VT_AI_Prep_v2_MASTER_SPEC.md.

This is NOT a DB model. It is a plain dict that callers pass to prompt builders.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List, Optional

if TYPE_CHECKING:
    from app.models.therapist import TherapistProfile
    from app.models.signature import TherapistSignatureProfile


def build_therapist_style_profile(
    profile: "TherapistProfile",
    signature: Optional["TherapistSignatureProfile"],
) -> Dict:
    """
    Merge TherapistProfile + TherapistSignatureProfile into one style dict.

    Implements spec §3.1.
    Safe to call with signature=None or an inactive signature; in that case all
    learned-style fields are set to None / appropriate defaults.
    """
    # ── TherapistProfile fields ──────────────────────────────────────────────
    profession: str = getattr(profile, "profession", None) or ""

    # therapeutic_approach is a SQLAlchemy Enum; extract its string value safely
    approach_raw = getattr(profile, "therapeutic_approach", None)
    therapeutic_approach: str = (
        approach_raw.value if hasattr(approach_raw, "value") else str(approach_raw or "")
    )

    primary_therapy_modes: List[str] = list(
        getattr(profile, "primary_therapy_modes", None) or []
    )
    tone: str = getattr(profile, "tone", None) or ""
    tone_warmth: int = getattr(profile, "tone_warmth", None) or 3
    directiveness: int = getattr(profile, "directiveness", None) or 3
    message_length_preference: str = getattr(profile, "message_length_preference", None) or "medium"
    style_version: int = getattr(profile, "style_version", None) or 1

    # common_terminology is a JSON list of strings; convert to {term: freq=1} dict
    terminology_raw = getattr(profile, "common_terminology", None) or []
    preferred_terminology: Dict[str, int] = (
        {str(t): 1 for t in terminology_raw if t}
        if isinstance(terminology_raw, list)
        else {}
    )

    # ── TherapistSignatureProfile fields (only if present and active) ────────
    sig_active = (
        signature is not None
        and getattr(signature, "is_active", False)
    )

    style_summary: Optional[str] = getattr(signature, "style_summary", None) if sig_active else None
    raw_examples = getattr(signature, "style_examples", None) if sig_active else None
    style_examples: List[str] = list(raw_examples) if isinstance(raw_examples, list) else []
    preferred_sentence_length: Optional[str] = (
        getattr(signature, "preferred_sentence_length", None) if sig_active else None
    )
    preferred_voice: Optional[str] = (
        getattr(signature, "preferred_voice", None) if sig_active else None
    )
    uses_clinical_jargon: bool = bool(
        getattr(signature, "uses_clinical_jargon", False) if sig_active else False
    )

    # Signature preferred_terminology is {term: freq} — merge with profile terms
    sig_terminology: Dict[str, int] = {}
    if sig_active:
        raw = getattr(signature, "preferred_terminology", None) or {}
        if isinstance(raw, dict):
            sig_terminology = {str(k): int(v) for k, v in raw.items()}
    # Profile terms take precedence if overlapping
    merged_terminology = {**sig_terminology, **preferred_terminology}

    return {
        "therapist_id": profile.therapist_id,
        "profession": profession,
        "therapeutic_approach": therapeutic_approach,
        "primary_therapy_modes": primary_therapy_modes,
        "tone": tone,
        "tone_warmth": tone_warmth,
        "directiveness": directiveness,
        "message_length_preference": message_length_preference,
        "style_summary": style_summary,
        "style_examples": style_examples,
        "preferred_sentence_length": preferred_sentence_length,
        "preferred_voice": preferred_voice,
        "uses_clinical_jargon": uses_clinical_jargon,
        "preferred_terminology": merged_terminology,
        "style_version": style_version,
    }
