"""AI Context Helper — builds the protocol/professional context dict
that is injected into every AI prompt.

Usage:
    ctx = build_ai_context_for_patient(profile, patient)
    block = format_protocol_block(ctx)   # empty string when no protocols
    prompt += block
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, List, Optional

from app.core.protocols import get_system_protocols, merge_protocols
from app.core.protocol_context import build_protocol_context_for_patient

if TYPE_CHECKING:
    from app.models.therapist import TherapistProfile
    from app.models.patient import Patient


def build_ai_context_for_patient(
    profile: Optional["TherapistProfile"],
    patient: Optional["Patient"],
    session_count: Optional[int] = None,
) -> dict:
    """
    Build the AI protocol/professional context dict for a therapist+patient pair.

    Returns a dict with three keys: "therapist", "patient", "protocols".
    Returns {} when no meaningful protocol context is available so callers can
    skip injection with a simple ``if ctx:`` check.

    Args:
        profile:       TherapistProfile ORM row (or None).
        patient:       Patient ORM row (or None).
        session_count: Optional total number of documented sessions for this patient.
                       When provided, each protocol entry gains a ``completed_sessions``
                       field so the AI can infer treatment phase.

    Resolution rules:
    - patient.protocol_ids (non-empty) overrides therapist.protocols_used
    - Protocols are resolved to full objects from system library + custom_protocols
    - Deduplication is handled by build_protocol_context_for_patient
    """
    if profile is None:
        return {}

    # ── Therapist section ──────────────────────────────────────────────────────

    profession: str = getattr(profile, "profession", None) or ""
    approaches: List[str] = list(getattr(profile, "primary_therapy_modes", None) or [])

    # years_of_experience stored as string ("8" or "10-15"); coerce to int best-effort
    yoe_raw = getattr(profile, "years_of_experience", None) or ""
    experience_years: Optional[int] = None
    try:
        experience_years = int(str(yoe_raw).split("-")[0].strip())
    except (ValueError, AttributeError):
        pass

    specialties_raw: str = getattr(profile, "areas_of_expertise", None) or ""
    specialties: List[str] = [s.strip() for s in specialties_raw.split(",") if s.strip()]

    protocols_used_ids: List[str] = list(getattr(profile, "protocols_used", None) or [])
    custom_protocols_raw: List[dict] = list(getattr(profile, "custom_protocols", None) or [])

    # ── Patient section ────────────────────────────────────────────────────────

    demographics: dict = {}
    patient_protocol_ids: List[str] = []

    if patient is not None:
        demographics = dict(getattr(patient, "demographics", None) or {})
        patient_protocol_ids = list(getattr(patient, "protocol_ids", None) or [])

    # ── Protocol resolution ────────────────────────────────────────────────────

    system_protocols = get_system_protocols()
    merged_library = merge_protocols(system_protocols, custom_protocols_raw)
    library_by_id = {p.id: p for p in merged_library}

    ctx_result = build_protocol_context_for_patient(
        therapist_protocol_ids=protocols_used_ids,
        therapist_custom_protocols=custom_protocols_raw,
        patient_protocol_ids=patient_protocol_ids if patient_protocol_ids else None,
    )

    active_ids: List[str] = [p["id"] for p in ctx_result.get("active_protocols", [])]

    # Nothing to inject if neither side has protocols
    if not active_ids and not protocols_used_ids:
        return {}

    resolved_protocols = []
    for pid in active_ids:
        p = library_by_id.get(pid)
        if p:
            entry: dict = {
                "id": p.id,
                "name": p.name,
                "approach": p.approach_id,
                "target_problem": p.target_problem,
                "description": p.description,
                "typical_sessions": p.typical_sessions,
                "core_techniques": p.core_techniques,
            }
            if session_count is not None:
                entry["completed_sessions"] = session_count
            resolved_protocols.append(entry)

    primary_protocol_id = active_ids[0] if active_ids else None

    return {
        "therapist": {
            "profession": profession,
            "approaches": approaches,
            "experience_years": experience_years,
            "specialties": specialties,
            "favorite_protocol_ids": protocols_used_ids,
        },
        "patient": {
            "age": demographics.get("age"),
            "marital_status": demographics.get("marital_status"),
            "has_guardian": demographics.get("has_guardian", False),
            "guardian_name": demographics.get("guardian_name", ""),
            "secondary_contact": demographics.get("parent_name", ""),
            "protocol_ids": active_ids,
            "primary_protocol_id": primary_protocol_id,
        },
        "protocols": resolved_protocols,
    }


# ── Prompt block formatter ─────────────────────────────────────────────────────

_WRAPPER_HEADER = """\

---

Professional and protocol context (JSON):

The JSON block below describes:
- the therapist's professional background and preferred protocols,
- the patient's basic profile and selected protocols (if any),
- the full definitions of the relevant protocols.

Use this JSON ONLY as context to guide your clinical reasoning.
Do NOT repeat, translate, or rewrite the JSON itself.
Base your reasoning on the documented session data; if the JSON and sessions conflict,
prefer the documented sessions.

The final clinical output MUST be written in fluent professional Hebrew.

[AI_PROTOCOL_CONTEXT]
"""

_WRAPPER_FOOTER = "\n[/AI_PROTOCOL_CONTEXT]"


def format_protocol_block(ctx: Optional[dict]) -> str:
    """
    Serialize ctx into the English-wrapped [AI_PROTOCOL_CONTEXT] block.

    Returns empty string when ctx is empty or has no protocols, so callers can
    unconditionally do:  prompt += format_protocol_block(ctx)
    """
    if not ctx:
        return ""
    if not ctx.get("protocols") and not ctx.get("patient", {}).get("protocol_ids"):
        return ""
    json_block = json.dumps(ctx, ensure_ascii=False, indent=2)
    return _WRAPPER_HEADER + json_block + _WRAPPER_FOOTER
