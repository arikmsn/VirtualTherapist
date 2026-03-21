"""
LLMContextEnvelope — central input contract for all AI pipelines.

Implements spec sections §4.1 and §4.2 of VT_AI_Prep_v2_MASTER_SPEC.md.

Usage (Phase 1 — debug only):
    envelope = build_llm_context_envelope_for_session(
        therapist, profile, signature, patient, modality_pack,
        summaries, request_type='prep', request_mode='deep',
    )
    logger.debug(f"envelope sessions={envelope['patient_state']['metadata']['sessions_analyzed']}")

Usage (Phase 2 — wired into PrepPipeline):
    prep_json = await pipeline.extract_only(envelope)
    async for chunk in pipeline.render_stream(envelope, prep_json):
        ...
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Literal, Optional

if TYPE_CHECKING:
    from app.models.therapist import Therapist, TherapistProfile
    from app.models.patient import Patient
    from app.models.modality import ModalityPack
    from app.models.session import SessionSummary
    from app.models.signature import TherapistSignatureProfile

from app.ai.state import build_patient_treatment_state
from app.ai.style import build_therapist_style_profile
from app.ai.constraints import build_ai_constraints

# Valid request_type values (spec §4.1)
_REQUEST_TYPES = frozenset({
    "prep",
    "session_summary",
    "deep_summary",
    "treatment_plan",
    "message",
    "homework",
})


def build_llm_context_envelope_for_session(
    therapist: "Therapist",
    profile: "TherapistProfile",
    signature: Optional["TherapistSignatureProfile"],
    patient: "Patient",
    modality_pack: Optional["ModalityPack"],
    summaries: "List[SessionSummary]",   # approved_by_therapist=True, ASC order
    request_type: str,
    request_mode: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Build a LLMContextEnvelope by calling all three sub-builders.

    Implements spec §4.2.
    All three sub-builders are pure Python — no LLM, no DB queries.
    Raises ValueError for unrecognised request_type.
    """
    if request_type not in _REQUEST_TYPES:
        raise ValueError(
            f"Unknown request_type {request_type!r}. Must be one of: {sorted(_REQUEST_TYPES)}"
        )

    therapist_style = build_therapist_style_profile(profile, signature)
    ai_constraints = build_ai_constraints(profile, modality_pack)
    patient_state = build_patient_treatment_state(
        therapist=therapist,
        profile=profile,
        patient=patient,
        modality_pack=modality_pack,
        summaries=summaries,
    )

    return {
        "therapist_style": therapist_style,
        "ai_constraints": ai_constraints,
        "patient_state": patient_state,
        "request_type": request_type,
        "request_mode": request_mode,
        "extra": dict(extra) if extra else {},
    }
