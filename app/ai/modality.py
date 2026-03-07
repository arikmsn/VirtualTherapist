"""
Modality pack resolution and system prompt assembly for Phase 2.

Three-layer prompt assembly (LLM reads top to bottom):
  Layer 1: modality_pack.prompt_module  — clinical method framing
  Layer 2: signature_module             — therapist style mirror (Phase 6, empty now)
  Layer 3: HEBREW_QUALITY_RULE          — language / format guardrail
  Layer 4: base_prompt                  — persona + therapist profile (from agent)
"""

from __future__ import annotations

from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session
    from app.models.modality import ModalityPack


HEBREW_QUALITY_RULE = """\
## כלל איכות חובה (עברית):
- כל פלט בעברית מקצועית שוטפת
- פתח תמיד בשדה full_summary לפני שאר השדות
- אל תשתמש בז'רגון קליני אנגלי אלא אם המטפל ביקש זאת במפורש
"""


def is_cbt_active(profile) -> bool:
    """
    Return True if the therapist has CBT in their active modalities.

    Checks both:
    - approach_description (CSV string, e.g. "CBT, psychodynamic") — set by frontend
    - therapeutic_approach (single enum value, e.g. TherapeuticApproach.CBT)

    Strictly opt-in: any non-CBT therapist gets False and is completely unaffected.
    """
    if not profile:
        return False
    if profile.approach_description:
        values = [v.strip() for v in profile.approach_description.split(",")]
        if "CBT" in values:
            return True
    if profile.therapeutic_approach and str(profile.therapeutic_approach).upper() == "CBT":
        return True
    return False


def resolve_modality_pack(db: "Session", therapist_id: int) -> Optional["ModalityPack"]:
    """
    Return the active ModalityPack for the given therapist.

    Resolution order:
    1. therapist_profiles.modality_pack_id  — explicit therapist choice
    2. Auto-detect CBT from approach_description / therapeutic_approach
    3. Fallback to 'generic_integrative'    — safe default
    4. None                                 — no packs in DB at all
    """
    from app.models.therapist import TherapistProfile
    from app.models.modality import ModalityPack

    profile = (
        db.query(TherapistProfile)
        .filter(TherapistProfile.therapist_id == therapist_id)
        .first()
    )

    if profile and profile.modality_pack_id:
        pack = (
            db.query(ModalityPack)
            .filter(
                ModalityPack.id == profile.modality_pack_id,
                ModalityPack.is_active == True,  # noqa: E712
            )
            .first()
        )
        if pack:
            return pack

    # Auto-detect CBT from therapist modalities
    if is_cbt_active(profile):
        cbt_pack = (
            db.query(ModalityPack)
            .filter(
                ModalityPack.name == "cbt",
                ModalityPack.is_active == True,  # noqa: E712
            )
            .first()
        )
        if cbt_pack:
            return cbt_pack

    # Fallback: generic_integrative
    return (
        db.query(ModalityPack)
        .filter(
            ModalityPack.name == "generic_integrative",
            ModalityPack.is_active == True,  # noqa: E712
        )
        .first()
    )


def assemble_system_prompt(
    base_prompt: str,
    modality_pack: Optional["ModalityPack"] = None,
) -> str:
    """
    Compose the final system prompt by prepending modality and quality layers.

    Result (top to bottom — what the LLM reads):
      [modality_pack.prompt_module]
      [HEBREW_QUALITY_RULE]
      [base_prompt — persona + therapist profile]

    Signature module (Layer 2 per spec) is empty in Phase 2; Phase 6 will inject it
    between the modality module and the quality rule.
    """
    layers: list[str] = []

    if modality_pack and modality_pack.prompt_module:
        layers.append(modality_pack.prompt_module.strip())

    layers.append(HEBREW_QUALITY_RULE.strip())
    layers.append(base_prompt.strip())

    return "\n\n".join(layers)
