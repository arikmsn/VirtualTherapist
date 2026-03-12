"""Background AI precompute jobs.

Each function:
  - Opens its own DB session (independent of the request lifecycle)
  - Builds a real AI provider via TherapistService
  - Delegates to the service's _precompute_to_cache method
  - Commits, closes, and never raises (best-effort)

Invoked via asyncio.create_task() from approve_summary / approve_deep_summary
so they run fire-and-forget without blocking the API response.
"""

from loguru import logger


async def precompute_prep_for_patient(
    patient_id: int,
    therapist_id: int,
) -> None:
    """
    Precompute a 'concise' prep brief for upcoming and recent sessions.

    Called when a summary is approved.  Warms cache for:
      1. All upcoming sessions (session_date >= today)
      2. The most recent past session (fallback if no upcoming exist)
    Each session gets its own precompute call; fingerprint checks inside
    generate_prep_v2 skip sessions whose cache is already valid.
    """
    from app.core.database import SessionLocal
    from app.models.session import Session as TherapySession
    from app.services.therapist_service import TherapistService
    from datetime import date

    db = SessionLocal()
    try:
        # Collect sessions to precompute: all upcoming + most recent past
        sessions_to_warm = list(
            db.query(TherapySession)
            .filter(
                TherapySession.patient_id == patient_id,
                TherapySession.therapist_id == therapist_id,
                TherapySession.session_date >= date.today(),
            )
            .order_by(TherapySession.session_date.asc())
            .limit(5)  # cap at 5 upcoming to avoid runaway work
            .all()
        )
        if not sessions_to_warm:
            # Fallback: most recent past session
            fallback = (
                db.query(TherapySession)
                .filter(
                    TherapySession.patient_id == patient_id,
                    TherapySession.therapist_id == therapist_id,
                )
                .order_by(TherapySession.session_date.desc())
                .first()
            )
            if fallback:
                sessions_to_warm = [fallback]

        if not sessions_to_warm:
            logger.debug(
                f"[precompute_prep] patient={patient_id} — no sessions found, skip"
            )
            return

        ts = TherapistService(db)
        agent = await ts.get_agent_for_therapist(therapist_id)

        from app.services.session_service import SessionService
        from app.ai.prep import PrepMode

        svc = SessionService(db)
        warmed_ids = []
        for session in sessions_to_warm:
            try:
                await svc._precompute_prep_to_cache(
                    session=session,
                    therapist_id=therapist_id,
                    mode=PrepMode.CONCISE,
                    agent=agent,
                )
                db.commit()
                warmed_ids.append(session.id)
            except Exception as exc:
                logger.warning(
                    f"[precompute_prep] patient={patient_id} session={session.id} "
                    f"failed (continuing): {exc!r}"
                )
                try:
                    db.rollback()
                except Exception:
                    pass

        logger.info(
            f"[precompute_prep] patient={patient_id} sessions={warmed_ids} — done"
        )
    except Exception as exc:
        logger.exception(
            f"[precompute_prep] patient={patient_id} failed (non-blocking): {exc!r}"
        )
        try:
            db.rollback()
        except Exception:
            pass
    finally:
        db.close()


async def precompute_deep_summary(
    patient_id: int,
    therapist_id: int,
) -> None:
    """
    Precompute a deep summary and store it in the patient cache columns.

    Called when a summary is approved.
    Skips if the existing cache is still valid (same fingerprint + within TTL).
    """
    from app.core.database import SessionLocal
    from app.services.deep_summary_service import DeepSummaryService
    from app.services.therapist_service import TherapistService

    db = SessionLocal()
    try:
        ts = TherapistService(db)
        agent = await ts.get_agent_for_therapist(therapist_id)

        svc = DeepSummaryService(db)
        warmed = await svc._precompute_to_cache(
            patient_id=patient_id,
            therapist_id=therapist_id,
            provider=agent.provider,
        )
        db.commit()
        if warmed:
            logger.info(f"[precompute_deep_summary] patient={patient_id} — done")
        else:
            logger.info(f"[precompute_deep_summary] patient={patient_id} — skipped (cache valid or no data)")
    except Exception as exc:
        logger.exception(
            f"[precompute_deep_summary] patient={patient_id} failed (non-blocking): {exc!r}"
        )
        try:
            db.rollback()
        except Exception:
            pass
    finally:
        db.close()


async def precompute_treatment_plan(
    patient_id: int,
    therapist_id: int,
) -> None:
    """
    Precompute a treatment plan and store it in the patient cache columns.

    Called when a deep summary is approved.
    Skips if the existing cache is still valid.
    """
    from app.core.database import SessionLocal
    from app.services.treatment_plan_service import TreatmentPlanService
    from app.services.therapist_service import TherapistService

    db = SessionLocal()
    try:
        ts = TherapistService(db)
        agent = await ts.get_agent_for_therapist(therapist_id)

        svc = TreatmentPlanService(db)
        warmed = await svc._precompute_to_cache(
            patient_id=patient_id,
            therapist_id=therapist_id,
            provider=agent.provider,
        )
        db.commit()
        if warmed:
            logger.info(f"[precompute_treatment_plan] patient={patient_id} — done")
        else:
            logger.info(f"[precompute_treatment_plan] patient={patient_id} — skipped (cache valid or no data)")
    except Exception as exc:
        logger.exception(
            f"[precompute_treatment_plan] patient={patient_id} failed (non-blocking): {exc!r}"
        )
        try:
            db.rollback()
        except Exception:
            pass
    finally:
        db.close()
