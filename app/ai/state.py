"""
PatientTreatmentState — computed per-patient clinical snapshot.

Implements spec sections §2.2 and §2.3 of VT_AI_Prep_v2_MASTER_SPEC.md.

This is NOT a DB model. It is a pure Python dict built on demand from
existing ORM objects (Therapist, TherapistProfile, Patient, ModalityPack,
List[SessionSummary]).  No LLM calls.  No DB writes.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from loguru import logger

if TYPE_CHECKING:
    from sqlalchemy.orm import Session as DBSession
    from app.models.therapist import Therapist, TherapistProfile
    from app.models.patient import Patient
    from app.models.modality import ModalityPack
    from app.models.session import SessionSummary


# Bumping this int invalidates any snapshot version checks in future phases.
_STATE_VERSION = 1


# ── Internal helpers ──────────────────────────────────────────────────────────

def _infer_phase(session_count: int, typical_sessions: Optional[int]) -> str:
    """Return 'early' | 'middle' | 'late' | 'undefined' from completion ratio."""
    if not typical_sessions or typical_sessions <= 0:
        return "undefined"
    ratio = session_count / typical_sessions
    if ratio < 1 / 3:
        return "early"
    if ratio <= 2 / 3:
        return "middle"
    return "late"


def _flatten_topics(summaries: "List[SessionSummary]") -> List[str]:
    """
    Flatten topics_discussed across all summaries, sorted by frequency descending.
    Deduplicates while preserving the most-mentioned themes first.
    """
    freq: Dict[str, int] = {}
    for s in summaries:
        topics = s.topics_discussed
        if not topics:
            continue
        if isinstance(topics, str):
            try:
                import json as _j
                topics = _j.loads(topics)
            except Exception:
                topics = [topics]
        for t in (topics if isinstance(topics, list) else []):
            if t and isinstance(t, str):
                key = t.strip()
                if key:
                    freq[key] = freq.get(key, 0) + 1
    return [t for t, _ in sorted(freq.items(), key=lambda x: -x[1])]


def _collect_risks(
    summaries: "List[SessionSummary]",
) -> tuple:
    """Return (has_active_risk: bool, descriptions: list, last_session_id: int|None)."""
    _trivial = {"none", "אין", "לא רלוונטי", "n/a", "-", ""}
    descriptions: List[str] = []
    last_session_id: Optional[int] = None
    for s in summaries:
        text = (s.risk_assessment or "").strip()
        if text.lower() not in _trivial:
            descriptions.append(text)
            last_session_id = s.id
    return bool(descriptions), descriptions, last_session_id


# ── Builder ───────────────────────────────────────────────────────────────────

def build_patient_treatment_state(
    therapist: "Therapist",
    profile: "TherapistProfile",
    patient: "Patient",
    modality_pack: Optional["ModalityPack"],
    summaries: "List[SessionSummary]",   # approved_by_therapist=True, ASC order
) -> Dict[str, Any]:
    """
    Build a PatientTreatmentState dict from existing ORM objects.

    Implements spec §2.2 and §2.3.
    Pure Python — no LLM, no DB writes.
    All fields not available today are set to [] / None (Phase 1 limitations noted).
    """
    now = datetime.utcnow()

    # ── 1. protocol_context (spec §2.2 item 1) ──────────────────────────────
    from app.core.ai_context import build_ai_context_for_patient

    ai_ctx = build_ai_context_for_patient(profile, patient, session_count=len(summaries))
    protocols_list: List[Dict] = ai_ctx.get("protocols", [])
    patient_ctx: Dict = ai_ctx.get("patient", {})
    primary_protocol_id: Optional[str] = patient_ctx.get("primary_protocol_id")

    # Phase inferred from the primary protocol's typical_sessions
    typical_sessions: Optional[int] = protocols_list[0].get("typical_sessions") if protocols_list else None
    phase = _infer_phase(len(summaries), typical_sessions)

    protocol_context: Dict[str, Any] = {
        "primary_protocol_id": primary_protocol_id,
        "protocols": protocols_list,
        "phase": phase,
    }

    # ── 2. longitudinal_state (spec §2.2 item 2) ────────────────────────────
    primary_themes = _flatten_topics(summaries)

    # active_goals from Patient.treatment_goals (JSON list)
    raw_goals = getattr(patient, "treatment_goals", None) or []
    active_goals: List[str] = [str(g) for g in raw_goals] if isinstance(raw_goals, list) else []

    # coping_strengths: Phase 1 heuristic — raw patient_progress text per session.
    # Proper strength/challenge parsing requires LLM (deferred to Phase 2).
    coping_strengths: List[str] = [
        (s.patient_progress or "").strip()
        for s in summaries
        if (s.patient_progress or "").strip()
    ]

    # persistent_challenges: topics that appear in ≥2 sessions
    topic_freq: Dict[str, int] = {}
    for s in summaries:
        topics = s.topics_discussed
        if topics and isinstance(topics, list):
            for t in topics:
                if t and isinstance(t, str):
                    k = t.strip()
                    topic_freq[k] = topic_freq.get(k, 0) + 1
    persistent_challenges: List[str] = [t for t, cnt in topic_freq.items() if cnt >= 2]

    longitudinal_state: Dict[str, Any] = {
        "primary_themes": primary_themes,
        "active_goals": active_goals,
        "coping_strengths": coping_strengths,
        "persistent_challenges": persistent_challenges,
    }

    # ── 3. last_session_state (spec §2.2 item 3) ────────────────────────────
    last_s = summaries[-1] if summaries else None
    if last_s:
        # session_number lives on TherapySession, not SessionSummary.
        # Phase 1 limitation: set to None. Will be enriched in Phase 2 when
        # callers pass TherapySession objects instead of bare SessionSummary rows.
        hw = last_s.homework_assigned
        homework_given: Optional[str] = (
            hw if isinstance(hw, str) else (str(hw) if hw else None)
        )
        last_session_state: Dict[str, Any] = {
            "session_id": last_s.id,
            "session_number": None,  # Phase 1 limitation — not on SessionSummary ORM
            "key_points": last_s.topics_discussed or [],
            "homework_given": homework_given,
            "homework_status": None,  # no completion-tracking field today
            "risk_notes": (last_s.risk_assessment or "").strip() or None,
        }
    else:
        last_session_state = {
            "session_id": None,
            "session_number": None,
            "key_points": [],
            "homework_given": None,
            "homework_status": None,
            "risk_notes": None,
        }

    # ── 4. current_risks (spec §2.2 item 4) ─────────────────────────────────
    has_active_risk, risk_descriptions, last_risk_session_id = _collect_risks(summaries)
    current_risks: Dict[str, Any] = {
        "has_active_risk": has_active_risk,
        "risk_descriptions": risk_descriptions,
        "last_risk_update_session_id": last_risk_session_id,
    }

    # ── 5. homework_state (spec §2.2 item 5) ────────────────────────────────
    raw_exercises = getattr(patient, "current_exercises", None) or []
    open_homework_items: List = raw_exercises if isinstance(raw_exercises, list) else []
    homework_state: Dict[str, Any] = {
        "open_homework_items": open_homework_items,
        "recent_completions": [],   # no completion-tracking field today (Phase 1)
    }

    # ── 6. open_threads (spec §2.2 item 6) ──────────────────────────────────
    unresolved_topics: List[str] = []
    if last_s and last_s.next_session_plan:
        raw = last_s.next_session_plan.strip()
        if raw:
            parts = [p.strip() for p in re.split(r"\n|(?<=\.)\s+", raw) if p.strip()]
            unresolved_topics = parts if parts else [raw]
    open_threads: Dict[str, Any] = {
        "unresolved_topics": unresolved_topics,
        "assessment_due": [],   # no dedicated field today (Phase 1)
    }

    # ── 7. metadata (spec §2.2 item 7) ──────────────────────────────────────
    metadata: Dict[str, Any] = {
        "sessions_analyzed": len(summaries),
        "last_updated_at": now.isoformat(),
        "source": "computed",
        "version": _STATE_VERSION,
    }

    return {
        "patient_id": patient.id,
        "therapist_id": therapist.id,
        "protocol_context": protocol_context,
        "longitudinal_state": longitudinal_state,
        "last_session_state": last_session_state,
        "current_risks": current_risks,
        "homework_state": homework_state,
        "open_threads": open_threads,
        "metadata": metadata,
    }


# ── Background rebuild (spec §6.2, §6.3) ─────────────────────────────────────

async def rebuild_patient_treatment_state(
    db: "DBSession",
    patient_id: int,
    therapist_id: int,
) -> None:
    """
    Load DB objects, build PatientTreatmentState, and log at DEBUG.

    Implements spec §6.2 (rebuild_patient_treatment_state job) and §6.3
    (triggered after SessionSummary approval, best-effort background call).

    Phase 1: does NOT persist the result. Logs only.
    """
    try:
        from sqlalchemy.orm import joinedload
        from app.models.therapist import Therapist, TherapistProfile
        from app.models.patient import Patient
        from app.models.session import TherapySession

        therapist = db.query(Therapist).filter(Therapist.id == therapist_id).first()
        profile = db.query(TherapistProfile).filter(
            TherapistProfile.therapist_id == therapist_id
        ).first()
        patient = db.query(Patient).filter(Patient.id == patient_id).first()

        if not therapist or not profile or not patient:
            logger.debug(
                f"[rebuild_pts] patient={patient_id} therapist={therapist_id} "
                "— missing objects, skipping"
            )
            return

        modality_pack = None
        if profile.modality_pack_id:
            from app.models.modality import ModalityPack
            modality_pack = db.query(ModalityPack).filter(
                ModalityPack.id == profile.modality_pack_id
            ).first()

        # Load approved summaries (ORM objects), oldest → newest
        patient_sessions = (
            db.query(TherapySession)
            .options(joinedload(TherapySession.summary))
            .filter(
                TherapySession.patient_id == patient_id,
                TherapySession.summary_id.isnot(None),
            )
            .order_by(TherapySession.session_date.asc())
            .all()
        )
        summaries = [
            s.summary
            for s in patient_sessions
            if s.summary and s.summary.approved_by_therapist
        ]

        state = build_patient_treatment_state(
            therapist=therapist,
            profile=profile,
            patient=patient,
            modality_pack=modality_pack,
            summaries=summaries,
        )
        logger.debug(
            f"[rebuild_pts] patient={patient_id} therapist={therapist_id} "
            f"sessions={state['metadata']['sessions_analyzed']} "
            f"phase={state['protocol_context']['phase']} "
            f"themes={len(state['longitudinal_state']['primary_themes'])} "
            f"has_risk={state['current_risks']['has_active_risk']}"
        )
    except Exception as exc:
        logger.warning(
            f"[rebuild_pts] patient={patient_id} therapist={therapist_id} "
            f"— build failed (non-blocking): {exc!r}"
        )
