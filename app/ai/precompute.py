"""
Background precompute jobs for Prep, Deep Summary, and Treatment Plan.

Each job runs via asyncio.create_task() (fire-and-forget, non-blocking).
Each job creates its own DB session and closes it on completion.

Trigger points:
  precompute_prep_for_patient        → approve_summary, protocol_ids update
  precompute_deep_summary_for_patient → approve_summary (threshold-gated)
  precompute_treatment_plan_for_patient → deep_summary approval

Session attachment for Prep precompute:
  The job writes prep artifacts to the LATEST TherapySession (by session_date DESC)
  for this patient. Rationale: when a therapist approves summary N, the next time
  they need prep will be for that same session or the next one. Writing to the
  most-recent session means the therapist finds precomputed prep when they open it.
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Optional

from loguru import logger

# ── Freshness / threshold constants (all configurable here) ───────────────────

# Prep: serve from cache without an LLM call within this window
PREP_FRESH_SECONDS: int = 86_400          # 24 hours

# Deep summary: trigger precompute if latest is older than this
DEEP_SUMMARY_FRESHNESS_DAYS: int = 30

# Deep summary: trigger precompute if ≥ this many new summaries since last run
DEEP_SUMMARY_MIN_NEW_SUMMARIES: int = 3


# ── Shared helpers ────────────────────────────────────────────────────────────

def _load_context(db, patient_id: int):
    """
    Load (therapist, profile, patient, modality_pack) for a given patient.
    Raises ValueError if patient not found.
    """
    from app.models.patient import Patient
    from app.models.therapist import Therapist, TherapistProfile
    from app.models.modality import ModalityPack

    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise ValueError(f"Patient {patient_id} not found")

    therapist_id = patient.therapist_id
    therapist = db.query(Therapist).filter(Therapist.id == therapist_id).first()
    profile = (
        db.query(TherapistProfile)
        .filter(TherapistProfile.therapist_id == therapist_id)
        .first()
    )
    modality_pack = None
    if profile and profile.modality_pack_id:
        modality_pack = (
            db.query(ModalityPack)
            .filter(ModalityPack.id == profile.modality_pack_id)
            .first()
        )
    return therapist, profile, patient, modality_pack


def _load_approved_summary_orms(db, patient_id: int, therapist_id: int, limit: int = 10):
    """Return approved SessionSummary ORM objects, oldest → newest (up to limit)."""
    from sqlalchemy.orm import joinedload
    from app.models.session import Session as TherapySession

    rows = (
        db.query(TherapySession)
        .options(joinedload(TherapySession.summary))
        .filter(
            TherapySession.patient_id == patient_id,
            TherapySession.therapist_id == therapist_id,
            TherapySession.summary_id.isnot(None),
        )
        .order_by(TherapySession.session_date.asc())
        .all()
    )
    return [r.summary for r in rows if r.summary and r.summary.approved_by_therapist][-limit:]


def _load_approved_summary_dicts(
    db, patient_id: int, therapist_id: int, limit: int = 10
) -> list[dict]:
    """Return approved summary dicts for fingerprint computation, oldest → newest."""
    from sqlalchemy.orm import joinedload
    from app.models.session import Session as TherapySession

    rows = (
        db.query(TherapySession)
        .options(joinedload(TherapySession.summary))
        .filter(
            TherapySession.patient_id == patient_id,
            TherapySession.therapist_id == therapist_id,
            TherapySession.summary_id.isnot(None),
        )
        .order_by(TherapySession.session_date.asc())
        .all()
    )
    result = []
    for r in rows:
        if r.summary and r.summary.approved_by_therapist:
            result.append({
                "summary_id": r.summary.id,
                "approved_at": (
                    str(r.summary.edit_ended_at) if r.summary.edit_ended_at else None
                ),
                "full_summary": r.summary.full_summary,
            })
    return result[-limit:]


# ── Prep precompute ───────────────────────────────────────────────────────────

async def precompute_prep_for_patient(patient_id: int) -> None:
    """
    Background job: run Extraction + Render for this patient's upcoming session.

    Attaches the precomputed prep to the latest TherapySession (by session_date DESC).
    After this job completes, the next /prep request for that session is a cache hit
    (source=precomputed, ~1 s response time).

    Creates its own DB session — safe to call from asyncio.create_task().
    """
    from app.core.database import SessionLocal

    db = SessionLocal()
    t0 = time.monotonic()
    try:
        therapist, profile, patient, modality_pack = _load_context(db, patient_id)
        therapist_id = patient.therapist_id

        # Target: latest session for this patient
        from app.models.session import Session as TherapySession

        target_session = (
            db.query(TherapySession)
            .filter(TherapySession.patient_id == patient_id)
            .order_by(TherapySession.session_date.desc())
            .first()
        )
        if not target_session:
            logger.warning(
                f"[prep_precompute] patient={patient_id} no sessions found, skipping"
            )
            return

        summary_orms = _load_approved_summary_orms(db, patient_id, therapist_id)
        if not summary_orms:
            logger.warning(
                f"[prep_precompute] patient={patient_id} no approved summaries, skipping"
            )
            return

        # Signature
        from app.ai.signature import SignatureEngine

        sig_engine = SignatureEngine(db)
        sig_profile = await sig_engine.get_active_profile(therapist_id)

        # AI context (protocol block)
        from app.core.ai_context import build_ai_context_for_patient

        ai_ctx = build_ai_context_for_patient(profile, patient, session_count=len(summary_orms))

        # Build envelope
        from app.ai.context import build_llm_context_envelope_for_session

        modality_name = modality_pack.name if modality_pack else "generic_integrative"
        modality_prompt_module = modality_pack.prompt_module if modality_pack else None

        envelope = build_llm_context_envelope_for_session(
            therapist=therapist,
            profile=profile,
            signature=sig_profile,
            patient=patient,
            modality_pack=modality_pack,
            summaries=summary_orms,
            request_type="prep",
            request_mode="deep",
            extra={
                "modality": modality_name,
                "modality_prompt_module": modality_prompt_module,
                "ai_context": ai_ctx,
                "approved_sample_count": (
                    getattr(sig_profile, "approved_sample_count", 0) if sig_profile else 0
                ),
                "min_samples_required": (
                    getattr(sig_profile, "min_samples_required", 5) if sig_profile else 5
                ),
            },
        )

        # AI provider + pipeline
        from app.services.therapist_service import TherapistService
        from app.ai.prep import PrepPipeline

        agent = await TherapistService(db).get_agent_for_therapist(therapist_id)
        pipeline = PrepPipeline(agent)
        result = await pipeline.run_with_envelope(envelope)

        # Fingerprint for cache validation
        from app.core.fingerprint import compute_fingerprint, FINGERPRINT_VERSION

        approved_dicts = _load_approved_summary_dicts(db, patient_id, therapist_id)
        fp = compute_fingerprint({
            "mode": "deep",
            "summaries": approved_dicts,
            "style_version": getattr(profile, "style_version", 1) if profile else 1,
        })

        # Persist
        target_session.prep_json = result.prep_json
        target_session.prep_rendered_text = result.rendered_text
        target_session.prep_mode = "deep"
        target_session.prep_generated_at = datetime.utcnow()
        target_session.prep_input_fingerprint = fp
        target_session.prep_input_fingerprint_version = FINGERPRINT_VERSION
        db.commit()

        elapsed_ms = int((time.monotonic() - t0) * 1000)
        logger.warning(
            f"[prep_precompute] patient={patient_id} session={target_session.id} "
            f"sessions_analyzed={len(summary_orms)} time_ms={elapsed_ms}"
        )

    except Exception as exc:
        logger.warning(f"[prep_precompute] patient={patient_id} FAILED: {exc!r}")
    finally:
        db.close()


# ── Deep summary precompute ───────────────────────────────────────────────────

def _should_precompute_deep_summary(
    db, patient_id: int, therapist_id: int
) -> tuple[bool, str]:
    """
    Returns (should_run, reason_string).

    Triggers when:
      - No DeepSummary exists for this patient, OR
      - Latest deep summary is older than DEEP_SUMMARY_FRESHNESS_DAYS, OR
      - ≥ DEEP_SUMMARY_MIN_NEW_SUMMARIES approved summaries have been added
        since the last deep summary was generated.
    """
    from app.models.deep_summary import DeepSummary
    from sqlalchemy.orm import joinedload
    from app.models.session import Session as TherapySession

    latest_ds = (
        db.query(DeepSummary)
        .filter(
            DeepSummary.patient_id == patient_id,
            DeepSummary.therapist_id == therapist_id,
        )
        .order_by(DeepSummary.created_at.desc())
        .first()
    )

    if not latest_ds:
        return True, "no_existing_deep_summary"

    age_days = (datetime.utcnow() - latest_ds.created_at).days
    if age_days >= DEEP_SUMMARY_FRESHNESS_DAYS:
        return True, f"stale age_days={age_days}"

    # Count newly-approved summaries since last deep summary
    new_count = 0
    rows = (
        db.query(TherapySession)
        .options(joinedload(TherapySession.summary))
        .filter(
            TherapySession.patient_id == patient_id,
            TherapySession.therapist_id == therapist_id,
            TherapySession.summary_id.isnot(None),
        )
        .all()
    )
    for r in rows:
        if (
            r.summary
            and r.summary.approved_by_therapist
            and r.summary.edit_ended_at
            and r.summary.edit_ended_at > latest_ds.created_at
        ):
            new_count += 1

    if new_count >= DEEP_SUMMARY_MIN_NEW_SUMMARIES:
        return True, f"new_summaries={new_count}"

    return False, f"fresh age_days={age_days} new_since_last={new_count}"


async def precompute_deep_summary_for_patient(patient_id: int) -> None:
    """
    Background job: generate a deep summary and persist as status=draft.

    Uses threshold checks (see _should_precompute_deep_summary) — no-ops when
    the existing summary is fresh enough.

    Creates its own DB session — safe to call from asyncio.create_task().
    """
    from app.core.database import SessionLocal

    db = SessionLocal()
    t0 = time.monotonic()
    try:
        therapist, profile, patient, modality_pack = _load_context(db, patient_id)
        therapist_id = patient.therapist_id

        should_run, reason = _should_precompute_deep_summary(db, patient_id, therapist_id)
        if not should_run:
            logger.warning(
                f"[deep_precompute] patient={patient_id} skip reason={reason}"
            )
            return

        from app.services.therapist_service import TherapistService
        from app.services.deep_summary_service import DeepSummaryService

        agent = await TherapistService(db).get_agent_for_therapist(therapist_id)
        summary_count = len(_load_approved_summary_orms(db, patient_id, therapist_id))

        deep_summary = await DeepSummaryService(db).generate_deep_summary(
            patient_id=patient_id,
            therapist_id=therapist_id,
            provider=agent.provider,
        )
        db.commit()

        elapsed_ms = int((time.monotonic() - t0) * 1000)
        logger.warning(
            f"[deep_precompute] patient={patient_id} summaries={summary_count} "
            f"deep_summary_id={deep_summary.id} time_ms={elapsed_ms} reason={reason}"
        )

    except ValueError as exc:
        # Expected: no approved summaries yet, etc.
        logger.info(f"[deep_precompute] patient={patient_id} skipped: {exc}")
    except Exception as exc:
        logger.warning(f"[deep_precompute] patient={patient_id} FAILED: {exc!r}")
    finally:
        db.close()


# ── Treatment plan precompute ─────────────────────────────────────────────────

async def precompute_treatment_plan_for_patient(patient_id: int) -> None:
    """
    Background job: create or update treatment plan for this patient.

    - No active plan: creates a new one (version 1).
    - Active plan exists: updates it (increments version, archives old).

    Creates its own DB session — safe to call from asyncio.create_task().
    """
    from app.core.database import SessionLocal

    db = SessionLocal()
    t0 = time.monotonic()
    try:
        therapist, profile, patient, modality_pack = _load_context(db, patient_id)
        therapist_id = patient.therapist_id

        from app.services.therapist_service import TherapistService
        from app.services.treatment_plan_service import TreatmentPlanService

        agent = await TherapistService(db).get_agent_for_therapist(therapist_id)
        plan_service = TreatmentPlanService(db)

        existing = plan_service._get_active_plan(patient_id, therapist_id)
        if existing:
            plan = await plan_service.update_plan(
                patient_id=patient_id,
                therapist_id=therapist_id,
                session_ids=None,
                provider=agent.provider,
            )
        else:
            try:
                plan = await plan_service.create_plan(
                    patient_id=patient_id,
                    therapist_id=therapist_id,
                    session_ids=None,
                    provider=agent.provider,
                )
            except ValueError as exc:
                if "already exists" in str(exc):
                    # Race condition: created between our check and create — that's fine
                    plan = plan_service._get_active_plan(patient_id, therapist_id)
                else:
                    raise

        db.commit()

        elapsed_ms = int((time.monotonic() - t0) * 1000)
        logger.warning(
            f"[plan_precompute] patient={patient_id} "
            f"plan_id={plan.id if plan else 'unknown'} time_ms={elapsed_ms}"
        )

    except ValueError as exc:
        logger.info(f"[plan_precompute] patient={patient_id} skipped: {exc}")
    except Exception as exc:
        logger.warning(f"[plan_precompute] patient={patient_id} FAILED: {exc!r}")
    finally:
        db.close()
