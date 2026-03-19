"""Unified AI precompute + caching layer for Deep Summary and Treatment Plan.

Each feature's result is keyed by a content fingerprint of the inputs:
    fingerprint(sorted(approved_summary_ids + approved_at) + sorted(patient.protocol_ids))

If the latest stored artifact carries the same fingerprint, it is returned
immediately without an AI call (cache hit).  Otherwise the pipeline is called,
the fingerprint is stored on the new artifact, and it is returned.

Background precompute jobs call get_or_compute_* after clinical events (e.g.,
a summary approval).  They run in an isolated DB session so they never block or
break the caller's transaction.

Usage:
    # In a route handler — returns cache hit or freshly generated artifact:
    summary = await get_or_compute_deep_summary(db, patient_id, therapist_id, provider)

    # As a background task after summary approval:
    background_tasks.add_task(precompute_deep_summary_for_patient, therapist_id, patient_id)
"""
from __future__ import annotations

from typing import Optional

from loguru import logger
from sqlalchemy.orm import Session as DBSession

from app.core.fingerprint import FINGERPRINT_VERSION, compute_fingerprint
from app.models.deep_summary import DeepSummary
from app.models.patient import Patient
from app.models.session import Session as TherapySession
from app.models.session import SessionSummary
from app.models.treatment_plan import TreatmentPlan
from app.services.deep_summary_service import DeepSummaryService
from app.services.treatment_plan_service import TreatmentPlanService


# ---------------------------------------------------------------------------
# Shared fingerprint helper
# ---------------------------------------------------------------------------

def _compute_patient_fingerprint(db: DBSession, patient_id: int, therapist_id: int) -> str:
    """SHA-256 fingerprint of the clinical inputs shared by Deep Summary and Treatment Plan.

    Changes whenever:
    • a session summary is approved or its updated_at timestamp changes
    • a session summary is removed from the approved set (deletion / un-approve)
    • patient.protocol_ids is updated
    """
    approved = (
        db.query(SessionSummary.id, SessionSummary.updated_at)
        .join(TherapySession, TherapySession.summary_id == SessionSummary.id)
        .filter(
            TherapySession.patient_id == patient_id,
            TherapySession.therapist_id == therapist_id,
            SessionSummary.approved_by_therapist.is_(True),
        )
        .order_by(SessionSummary.id.asc())
        .all()
    )
    summary_tuples = [(s.id, str(s.updated_at)) for s in approved]

    patient = db.query(Patient.protocol_ids).filter(Patient.id == patient_id).first()
    protocol_ids = sorted(patient.protocol_ids or []) if patient else []

    return compute_fingerprint({
        "v": FINGERPRINT_VERSION,
        "summaries": summary_tuples,
        "protocol_ids": protocol_ids,
    })


# ---------------------------------------------------------------------------
# Deep Summary — get_or_compute
# ---------------------------------------------------------------------------

async def get_or_compute_deep_summary(
    db: DBSession,
    patient_id: int,
    therapist_id: int,
    provider,
) -> DeepSummary:
    """Return a fresh DeepSummary, hitting the cache when inputs are unchanged.

    Checks the latest stored deep summary's ``input_fingerprint`` against the
    current fingerprint.  On a match, returns the stored summary immediately
    (cache hit).  On a miss, calls the pipeline, saves the new fingerprint, and
    returns the new summary.
    """
    current_fp = _compute_patient_fingerprint(db, patient_id, therapist_id)

    latest = (
        db.query(DeepSummary)
        .filter(
            DeepSummary.patient_id == patient_id,
            DeepSummary.therapist_id == therapist_id,
        )
        .order_by(DeepSummary.created_at.desc())
        .first()
    )

    if (
        latest is not None
        and latest.input_fingerprint is not None
        and latest.input_fingerprint == current_fp
        and latest.input_fingerprint_version == FINGERPRINT_VERSION
    ):
        logger.info(
            f"[precompute] deep_summary cache HIT — "
            f"patient={patient_id} therapist={therapist_id} summary_id={latest.id} "
            f"fp={current_fp[:12]}"
        )
        return latest

    logger.info(
        f"[precompute] deep_summary cache MISS — "
        f"patient={patient_id} therapist={therapist_id} "
        f"stored_fp={latest.input_fingerprint[:12] if latest and latest.input_fingerprint else 'none'} "
        f"current_fp={current_fp[:12]}"
    )
    service = DeepSummaryService(db)
    new_summary = await service.generate_deep_summary(
        patient_id=patient_id,
        therapist_id=therapist_id,
        provider=provider,
    )
    # Persist the fingerprint so the next call can detect a cache hit
    new_summary.input_fingerprint = current_fp
    new_summary.input_fingerprint_version = FINGERPRINT_VERSION
    db.flush()
    return new_summary


# ---------------------------------------------------------------------------
# Treatment Plan — get_or_compute
# ---------------------------------------------------------------------------

async def get_or_compute_treatment_plan(
    db: DBSession,
    patient_id: int,
    therapist_id: int,
    provider,
    session_ids: Optional[list[int]] = None,
) -> TreatmentPlan:
    """Return a fresh TreatmentPlan, hitting the cache when inputs are unchanged.

    If the active plan's fingerprint matches current inputs, returns it immediately.
    If inputs changed: updates the plan (creating a new version) and saves the fingerprint.
    If no active plan exists: creates one.
    """
    current_fp = _compute_patient_fingerprint(db, patient_id, therapist_id)

    service = TreatmentPlanService(db)
    active_plan = service.get_active_plan(patient_id=patient_id, therapist_id=therapist_id)

    if (
        active_plan is not None
        and active_plan.input_fingerprint is not None
        and active_plan.input_fingerprint == current_fp
        and active_plan.input_fingerprint_version == FINGERPRINT_VERSION
    ):
        logger.info(
            f"[precompute] treatment_plan cache HIT — "
            f"patient={patient_id} therapist={therapist_id} plan_id={active_plan.id} "
            f"fp={current_fp[:12]}"
        )
        return active_plan

    logger.info(
        f"[precompute] treatment_plan cache MISS — "
        f"patient={patient_id} therapist={therapist_id} "
        f"stored_fp={active_plan.input_fingerprint[:12] if active_plan and active_plan.input_fingerprint else 'none'} "
        f"current_fp={current_fp[:12]} "
        f"action={'update' if active_plan else 'create'}"
    )
    if active_plan:
        plan = await service.update_plan(
            patient_id=patient_id,
            therapist_id=therapist_id,
            session_ids=session_ids,
            provider=provider,
        )
    else:
        plan = await service.create_plan(
            patient_id=patient_id,
            therapist_id=therapist_id,
            session_ids=session_ids,
            provider=provider,
        )
    plan.input_fingerprint = current_fp
    plan.input_fingerprint_version = FINGERPRINT_VERSION
    db.flush()
    return plan


# ---------------------------------------------------------------------------
# Background precompute jobs
# ---------------------------------------------------------------------------

async def precompute_deep_summary_for_patient(
    therapist_id: int,
    patient_id: int,
) -> None:
    """Best-effort: warm the deep summary cache for a patient after a clinical event.

    Creates its own DB session — never touches the caller's open transaction.
    All errors are logged and swallowed so they never reach the HTTP layer.
    """
    from app.core.database import SessionLocal
    from app.services.therapist_service import TherapistService

    logger.info(
        f"[precompute_deep_summary] START therapist={therapist_id} patient={patient_id}"
    )
    db = SessionLocal()
    try:
        therapist_service = TherapistService(db)
        agent = await therapist_service.get_agent_for_therapist(therapist_id)
        await get_or_compute_deep_summary(
            db=db,
            patient_id=patient_id,
            therapist_id=therapist_id,
            provider=agent.provider,
        )
        db.commit()
        logger.info(
            f"[precompute_deep_summary] DONE therapist={therapist_id} patient={patient_id}"
        )
    except Exception as exc:
        logger.warning(
            f"[precompute_deep_summary] FAILED therapist={therapist_id} "
            f"patient={patient_id}: {exc!r}"
        )
    finally:
        db.close()


async def precompute_treatment_plan_for_patient(
    therapist_id: int,
    patient_id: int,
) -> None:
    """Best-effort: warm the treatment plan cache for a patient after a clinical event.

    Creates its own DB session — never touches the caller's open transaction.
    All errors are logged and swallowed so they never reach the HTTP layer.
    """
    from app.core.database import SessionLocal
    from app.services.therapist_service import TherapistService

    logger.info(
        f"[precompute_treatment_plan] START therapist={therapist_id} patient={patient_id}"
    )
    db = SessionLocal()
    try:
        therapist_service = TherapistService(db)
        agent = await therapist_service.get_agent_for_therapist(therapist_id)
        await get_or_compute_treatment_plan(
            db=db,
            patient_id=patient_id,
            therapist_id=therapist_id,
            provider=agent.provider,
        )
        db.commit()
        logger.info(
            f"[precompute_treatment_plan] DONE therapist={therapist_id} patient={patient_id}"
        )
    except Exception as exc:
        logger.warning(
            f"[precompute_treatment_plan] FAILED therapist={therapist_id} "
            f"patient={patient_id}: {exc!r}"
        )
    finally:
        db.close()
