"""Treatment plan routes — Phase 7: Treatment Plan 2.0 + Drift Helper."""

from datetime import datetime
from typing import Any, Dict, List, Optional

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session as DBSession

from app.api.deps import get_db, get_current_therapist
from app.models.therapist import Therapist
from app.services.treatment_plan_service import TreatmentPlanService
from app.services.therapist_service import TherapistService
from loguru import logger

router = APIRouter()


# ── Request / Response schemas ────────────────────────────────────────────────

class CreatePlanRequest(BaseModel):
    session_ids: Optional[List[int]] = None   # if None, use all approved summaries


class UpdatePlanRequest(BaseModel):
    session_ids: Optional[List[int]] = None


class TreatmentPlanResponse(BaseModel):
    plan_id: int
    patient_id: int
    status: str
    version: int
    parent_version_id: Optional[int] = None
    plan_json: Optional[Dict[str, Any]] = None
    rendered_text: Optional[str] = None
    drift_score: Optional[float] = None
    drift_flags: Optional[List[str]] = None
    last_drift_check_at: Optional[datetime] = None
    approved_at: Optional[datetime] = None
    model_used: Optional[str] = None
    tokens_used: Optional[int] = None
    created_at: datetime


class TreatmentPlanListItem(BaseModel):
    plan_id: int
    status: str
    version: int
    parent_version_id: Optional[int] = None
    drift_score: Optional[float] = None
    approved_at: Optional[datetime] = None
    created_at: datetime
    rendered_text: Optional[str] = None
    plan_json: Optional[Dict[str, Any]] = None


class DriftCheckResponse(BaseModel):
    drift_score: float
    drift_flags: List[str]
    on_track_items: List[str]
    recommendation: str


# ── Helpers ───────────────────────────────────────────────────────────────────

def _plan_response(plan) -> TreatmentPlanResponse:
    return TreatmentPlanResponse(
        plan_id=plan.id,
        patient_id=plan.patient_id,
        status=plan.status,
        version=plan.version,
        parent_version_id=plan.parent_version_id,
        plan_json=plan.plan_json,
        rendered_text=plan.rendered_text,
        drift_score=plan.drift_score,
        drift_flags=plan.drift_flags,
        last_drift_check_at=plan.last_drift_check_at,
        approved_at=plan.approved_at,
        model_used=plan.model_used,
        tokens_used=plan.tokens_used,
        created_at=plan.created_at,
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post(
    "/clients/{client_id}/treatment-plan",
    status_code=202,
)
async def create_treatment_plan(
    client_id: int,
    request: CreatePlanRequest,
    force_sync: bool = False,
    current_therapist: Therapist = Depends(get_current_therapist),
    db: DBSession = Depends(get_db),
):
    """
    Generate a treatment plan for a patient.

    Default behavior (async, recommended):
      If an active plan already exists → return it immediately (no LLM call).
      If no plan → fire background precompute job and return {status: "generating"}.
      Poll GET /clients/{id}/treatment-plan to get the result.

    ?force_sync=true: run synchronously (legacy, blocks for ~60-90 s).
    """
    plan_service = TreatmentPlanService(db)

    # Return existing active plan immediately (read-only, no LLM)
    existing = plan_service.get_active_plan(
        patient_id=client_id,
        therapist_id=current_therapist.id,
    )
    if existing and not force_sync:
        return _plan_response(existing)

    if force_sync:
        # Legacy synchronous path
        therapist_service = TherapistService(db)
        try:
            agent = await therapist_service.get_agent_for_therapist(current_therapist.id)
            plan = await plan_service.create_plan(
                patient_id=client_id,
                therapist_id=current_therapist.id,
                session_ids=request.session_ids,
                provider=agent.provider,
            )
            db.commit()
            return _plan_response(plan)
        except ValueError as e:
            msg = str(e)
            if "already exists" in msg:
                raise HTTPException(status_code=409, detail=msg)
            raise HTTPException(status_code=400, detail=msg)
        except Exception as e:
            logger.exception(f"create_treatment_plan client={client_id} failed: {e!r}")
            raise HTTPException(
                status_code=500,
                detail="שגיאה זמנית בשמירת התוכנית הטיפולית, נסו שוב בעוד מספר דקות",
            )

    # Async path: fire background job, return immediately
    try:
        from app.ai.precompute import precompute_treatment_plan_for_patient
        asyncio.create_task(precompute_treatment_plan_for_patient(client_id))
    except RuntimeError:
        pass  # no event loop in tests

    return {
        "status": "generating",
        "message": "תוכנית טיפול מתחילה להיבנות ברקע. בדוק שוב בעוד מספר דקות.",
        "patient_id": client_id,
    }


@router.put(
    "/clients/{client_id}/treatment-plan",
    status_code=202,
)
async def update_treatment_plan(
    client_id: int,
    request: UpdatePlanRequest,
    force_sync: bool = False,
    current_therapist: Therapist = Depends(get_current_therapist),
    db: DBSession = Depends(get_db),
):
    """
    Update the active treatment plan (creates new version, archives old).

    Default (async): fire background precompute job and return {status: "generating"}.
    ?force_sync=true: run synchronously (blocks ~60-90 s).
    Returns 404 if no active plan exists — use POST to create one.
    """
    plan_service = TreatmentPlanService(db)
    existing = plan_service.get_active_plan(
        patient_id=client_id,
        therapist_id=current_therapist.id,
    )
    if not existing:
        raise HTTPException(status_code=404, detail="No active treatment plan found. Use POST to create one.")

    if force_sync:
        therapist_service = TherapistService(db)
        try:
            agent = await therapist_service.get_agent_for_therapist(current_therapist.id)
            plan = await plan_service.update_plan(
                patient_id=client_id,
                therapist_id=current_therapist.id,
                session_ids=request.session_ids,
                provider=agent.provider,
            )
            db.commit()
            return _plan_response(plan)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as e:
            logger.exception(f"update_treatment_plan client={client_id} failed: {e!r}")
            raise HTTPException(
                status_code=500,
                detail="שגיאה זמנית בשמירת התוכנית הטיפולית, נסו שוב בעוד מספר דקות",
            )

    # Async path: fire background job, return immediately
    try:
        from app.ai.precompute import precompute_treatment_plan_for_patient
        asyncio.create_task(precompute_treatment_plan_for_patient(client_id))
    except RuntimeError:
        pass  # no event loop in tests

    return {
        "status": "generating",
        "message": "עדכון תוכנית הטיפול החל ברקע. בדוק שוב בעוד מספר דקות.",
        "patient_id": client_id,
    }


@router.get(
    "/clients/{client_id}/treatment-plan",
    response_model=TreatmentPlanResponse,
)
async def get_treatment_plan(
    client_id: int,
    current_therapist: Therapist = Depends(get_current_therapist),
    db: DBSession = Depends(get_db),
):
    """
    Return the active treatment plan.

    If no plan exists yet, generates an initial protocol-based plan on the fly,
    saves it, and returns it. Never returns 404 — there is always a plan.
    """
    plan_service = TreatmentPlanService(db)
    therapist_service = TherapistService(db)
    try:
        plan = plan_service.get_active_plan(
            patient_id=client_id,
            therapist_id=current_therapist.id,
        )
        if not plan:
            # No plan yet — generate initial protocol-based plan synchronously
            logger.warning(
                "[treatment_plan] GET client=%s no plan found — generating initial plan",
                client_id,
            )
            try:
                agent = await therapist_service.get_agent_for_therapist(current_therapist.id)
                plan = await plan_service.create_plan(
                    patient_id=client_id,
                    therapist_id=current_therapist.id,
                    session_ids=None,
                    provider=agent.provider,
                )
                db.commit()
                logger.warning(
                    "[treatment_plan] GET client=%s initial plan created plan_id=%s",
                    client_id,
                    plan.id,
                )
            except ValueError as e:
                if "already exists" in str(e):
                    # Race condition: created between our check and create
                    plan = plan_service.get_active_plan(client_id, current_therapist.id)
                    if not plan:
                        raise HTTPException(status_code=500, detail="Treatment plan race condition")
                else:
                    raise HTTPException(status_code=400, detail=str(e))
            except Exception as e:
                logger.exception(f"get_treatment_plan initial generation client={client_id} failed: {e!r}")
                raise HTTPException(
                    status_code=500,
                    detail="שגיאה זמנית ביצירת התוכנית הטיפולית, נסו שוב בעוד מספר דקות",
                )
        return _plan_response(plan)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"get_treatment_plan client={client_id} failed: {e!r}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/clients/{client_id}/treatment-plan/history",
    response_model=List[TreatmentPlanListItem],
)
async def get_treatment_plan_history(
    client_id: int,
    current_therapist: Therapist = Depends(get_current_therapist),
    db: DBSession = Depends(get_db),
):
    """Return all plan versions ordered newest → oldest."""
    plan_service = TreatmentPlanService(db)
    try:
        plans = plan_service.get_plan_history(
            patient_id=client_id,
            therapist_id=current_therapist.id,
        )
        return [
            TreatmentPlanListItem(
                plan_id=p.id,
                status=p.status,
                version=p.version,
                parent_version_id=p.parent_version_id,
                drift_score=p.drift_score,
                approved_at=p.approved_at,
                created_at=p.created_at,
                rendered_text=p.rendered_text,
                plan_json=p.plan_json,
            )
            for p in plans
        ]
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"get_treatment_plan_history client={client_id} failed: {e!r}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/clients/{client_id}/treatment-plan/check-drift",
    response_model=DriftCheckResponse,
)
async def check_drift(
    client_id: int,
    current_therapist: Therapist = Depends(get_current_therapist),
    db: DBSession = Depends(get_db),
):
    """
    Manual drift check trigger — runs DriftChecker immediately and returns result.

    Returns 404 if no active plan, 422 if no approved summaries exist.
    """
    therapist_service = TherapistService(db)
    plan_service = TreatmentPlanService(db)

    try:
        agent = await therapist_service.get_agent_for_therapist(current_therapist.id)
        result = await plan_service.run_drift_check(
            patient_id=client_id,
            therapist_id=current_therapist.id,
            session_id=0,    # manual trigger — no specific session
            provider=agent.provider,
        )
        if result is None:
            raise HTTPException(
                status_code=404,
                detail="No active treatment plan or no approved summaries found",
            )
        db.commit()
        return DriftCheckResponse(
            drift_score=result.drift_score,
            drift_flags=result.drift_flags,
            on_track_items=result.on_track_items,
            recommendation=result.recommendation,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"check_drift client={client_id} failed: {e!r}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete(
    "/treatment-plans/{plan_id}",
    status_code=204,
)
async def delete_treatment_plan(
    plan_id: int,
    current_therapist: Therapist = Depends(get_current_therapist),
    db: DBSession = Depends(get_db),
):
    """Hard-delete a treatment plan version. Returns 404 if not found or wrong owner."""
    plan_service = TreatmentPlanService(db)
    try:
        plan_service.delete_plan(
            plan_id=plan_id,
            therapist_id=current_therapist.id,
        )
        db.commit()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception(f"delete_treatment_plan plan={plan_id} failed: {e!r}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch(
    "/treatment-plans/{plan_id}/approve",
    response_model=TreatmentPlanResponse,
)
async def approve_treatment_plan(
    plan_id: int,
    current_therapist: Therapist = Depends(get_current_therapist),
    db: DBSession = Depends(get_db),
):
    """Approve a treatment plan — sets approved_at timestamp."""
    plan_service = TreatmentPlanService(db)
    try:
        plan = plan_service.approve_plan(
            plan_id=plan_id,
            therapist_id=current_therapist.id,
        )
        db.commit()
        return _plan_response(plan)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception(f"approve_treatment_plan plan={plan_id} failed: {e!r}")
        raise HTTPException(status_code=500, detail=str(e))
