"""
AIConstraints — single object capturing all AI limits and rules.

Implements spec section §3.2 of VT_AI_Prep_v2_MASTER_SPEC.md.

Combines TherapistProfile.prohibitions / custom_rules / language with
modality-specific constraints from ModalityPack.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List, Literal, Optional

if TYPE_CHECKING:
    from app.models.therapist import TherapistProfile
    from app.models.modality import ModalityPack

# Language codes we recognise as valid; anything else falls back to 'he'.
_VALID_LANG_CODES = {"he", "en", "ar", "ru"}


def build_ai_constraints(
    profile: "TherapistProfile",
    modality_pack: Optional["ModalityPack"],
) -> Dict:
    """
    Build an AIConstraints dict from TherapistProfile and the active ModalityPack.

    Implements spec §3.2.
    Safe to call with modality_pack=None (fields are set to []).
    """
    # ── Language ─────────────────────────────────────────────────────────────
    raw_lang = (getattr(profile, "language", None) or "he").strip().lower()
    language: str = raw_lang if raw_lang in _VALID_LANG_CODES else "he"

    # ── Prohibitions (JSON list of strings) ──────────────────────────────────
    raw_prohibitions = getattr(profile, "prohibitions", None) or []
    prohibitions: List[str] = (
        [str(p) for p in raw_prohibitions if p]
        if isinstance(raw_prohibitions, list)
        else []
    )

    # ── Custom rules (Text field — split on newlines to produce a list) ──────
    raw_custom = (getattr(profile, "custom_rules", None) or "").strip()
    custom_rules: List[str] = (
        [line.strip() for line in raw_custom.splitlines() if line.strip()]
        if raw_custom
        else []
    )

    # ── Max length hint (derived from message_length_preference) ─────────────
    _length_map: Dict[str, str] = {
        "short": "short",
        "medium": "medium",
        "detailed": "detailed",
        "long": "detailed",   # alias
    }
    raw_len = (getattr(profile, "message_length_preference", None) or "medium").lower()
    max_length_hint: Literal["short", "medium", "detailed"] = _length_map.get(raw_len, "medium")  # type: ignore[assignment]

    # ── Modality-derived fields ───────────────────────────────────────────────
    if modality_pack is not None:
        modality_required_fields: List[str] = list(
            getattr(modality_pack, "required_summary_fields", None) or []
        )
        modality_recommended_fields: List[str] = list(
            getattr(modality_pack, "recommended_summary_fields", None) or []
        )
    else:
        modality_required_fields = []
        modality_recommended_fields = []

    return {
        "language": language,
        "prohibitions": prohibitions,
        "custom_rules": custom_rules,
        "max_length_hint": max_length_hint,
        "modality_required_fields": modality_required_fields,
        "modality_recommended_fields": modality_recommended_fields,
        "disallowed_behaviors": [],   # extensible in Phase 2
        "must_never_ending_with_question": True,   # hardcoded per spec §3.2
    }
