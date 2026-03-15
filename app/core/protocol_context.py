"""Protocol context builder — used by AI prompt construction.

``build_protocol_context_for_patient()`` returns a structured dict that can
be injected into any AI prompt (prep, session summary, deep summary,
treatment plan) to make the model aware of the active clinical protocols.

Priority rules:
  1. Patient's own ``protocol_ids`` (set per-patient in settings)
  2. Therapist's global ``protocols_used`` list (fallback when patient has none)
  3. Empty context (no protocol guidance injected)

Usage example::

    ctx = build_protocol_context_for_patient(
        therapist_protocol_ids=profile.protocols_used or [],
        therapist_custom_protocols=profile.custom_protocols or [],
        patient_protocol_ids=patient.protocol_ids or None,
    )
    if ctx["protocol_summary"]:
        prompt += f"\\n\\nActive protocols: {ctx['protocol_summary']}"

# TODO (future): inject ctx into session-summary, deep-summary, prep, and
# treatment-plan prompts once the protocol library is fully adopted.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from loguru import logger

from app.core.protocols import Protocol, get_system_protocols, merge_protocols


def build_protocol_context_for_patient(
    therapist_protocol_ids: List[str],
    therapist_custom_protocols: List[dict],
    patient_protocol_ids: Optional[List[str]],
) -> Dict[str, Any]:
    """Return a structured dict describing the active protocols for a prompt.

    Args:
        therapist_protocol_ids:    IDs of protocols the therapist uses globally.
        therapist_custom_protocols: Raw custom protocol dicts from DB JSON column.
        patient_protocol_ids:      IDs of protocols selected for *this* patient.
                                   ``None`` or empty → fall back to therapist list.

    Returns::

        {
            "active_protocols": [{"id": ..., "name": ..., ...}, ...],
            "source": "patient" | "therapist" | "none",
            "protocol_names": ["name", ...],
            "protocol_summary": "CBT לדיכאון (דיכאון קליני): מודל ABC, ... | ...",
        }
    """
    all_protocols = merge_protocols(
        get_system_protocols(),
        therapist_custom_protocols or [],
    )
    protocol_map: Dict[str, Protocol] = {p.id: p for p in all_protocols}

    # Decide which protocol IDs are authoritative for this patient
    if patient_protocol_ids and len(patient_protocol_ids) > 0:
        active_ids = patient_protocol_ids
        source = "patient"
    elif therapist_protocol_ids and len(therapist_protocol_ids) > 0:
        active_ids = therapist_protocol_ids
        source = "therapist"
    else:
        return {
            "active_protocols": [],
            "source": "none",
            "protocol_names": [],
            "protocol_summary": "",
        }

    active_protocols: List[Protocol] = []
    for pid in active_ids:
        p = protocol_map.get(pid)
        if p:
            active_protocols.append(p)
        else:
            logger.debug(
                f"[protocol_context] unknown protocol_id={pid!r} — skipping"
            )

    if not active_protocols:
        return {
            "active_protocols": [],
            "source": source,
            "protocol_names": [],
            "protocol_summary": "",
        }

    protocol_names = [p.name for p in active_protocols]

    # Build a compact summary string suitable for prompt injection
    summary_parts: List[str] = []
    for p in active_protocols:
        techniques = ", ".join(p.core_techniques[:4]) if p.core_techniques else ""
        part = f"{p.name} ({p.target_problem})"
        if techniques:
            part += f": {techniques}"
        summary_parts.append(part)

    return {
        "active_protocols": [p.model_dump() for p in active_protocols],
        "source": source,
        "protocol_names": protocol_names,
        "protocol_summary": " | ".join(summary_parts),
    }
