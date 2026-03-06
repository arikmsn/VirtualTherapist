"""Formal records routes — Israeli clinical documentation (Phase 5)."""

from datetime import datetime
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session as DBSession

from app.ai.formal_record import RecordType
from app.api.deps import get_db, get_current_therapist
from app.models.therapist import Therapist
from app.services.formal_record_service import FormalRecordService
from app.services.therapist_service import TherapistService
from loguru import logger

router = APIRouter()


# ── Request / Response schemas ────────────────────────────────────────────────

class CreateFormalRecordRequest(BaseModel):
    record_type: str
    session_ids: Optional[List[int]] = None     # if None, use all approved summaries
    additional_context: Optional[str] = None    # free text from therapist


class FormalRecordResponse(BaseModel):
    record_id: int
    rendered_text: Optional[str] = None
    record_json: Optional[Dict[str, Any]] = None
    record_type: str
    status: str
    approved_at: Optional[datetime] = None
    model_used: Optional[str] = None
    tokens_used: Optional[int] = None
    created_at: datetime


class FormalRecordListItem(BaseModel):
    record_id: int
    record_type: str
    status: str
    approved_at: Optional[datetime] = None
    created_at: datetime


class FormalRecordListResponse(BaseModel):
    records: List[FormalRecordListItem]
    total: int
    page: int
    per_page: int


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/patients/{patient_id}/formal-records", response_model=FormalRecordResponse, status_code=201)
async def create_formal_record(
    patient_id: int,
    request: CreateFormalRecordRequest,
    current_therapist: Therapist = Depends(get_current_therapist),
    db: DBSession = Depends(get_db),
):
    """
    Generate a formal clinical record for a patient.

    Auth: therapist must own the patient.
    Source of truth: only approved summaries (approved_by_therapist=True) are used.
    Returns the generated draft record.
    """
    try:
        record_type = RecordType(request.record_type)
    except ValueError:
        valid = [rt.value for rt in RecordType]
        raise HTTPException(
            status_code=422,
            detail=f"Invalid record_type '{request.record_type}'. Must be one of: {valid}",
        )

    therapist_service = TherapistService(db)
    formal_record_service = FormalRecordService(db)

    try:
        agent = await therapist_service.get_agent_for_therapist(current_therapist.id)
        record = await formal_record_service.create_formal_record(
            patient_id=patient_id,
            therapist_id=current_therapist.id,
            record_type=record_type,
            session_ids=request.session_ids,
            additional_context=request.additional_context,
            provider=agent.provider,
        )
        db.commit()
        return FormalRecordResponse(
            record_id=record.id,
            rendered_text=record.rendered_text,
            record_json=record.record_json,
            record_type=record.record_type,
            status=record.status,
            approved_at=record.approved_at,
            model_used=record.model_used,
            tokens_used=record.tokens_used,
            created_at=record.created_at,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        logger.exception(f"create_formal_record patient={patient_id} RuntimeError: {e!r}")
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.exception(f"create_formal_record patient={patient_id} failed: {e!r}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/formal-records/{record_id}/approve", response_model=FormalRecordResponse)
async def approve_formal_record(
    record_id: int,
    current_therapist: Therapist = Depends(get_current_therapist),
    db: DBSession = Depends(get_db),
):
    """
    Approve a formal record — sets status to 'approved' and records timestamp.
    Only the owning therapist can approve.
    """
    formal_record_service = FormalRecordService(db)
    try:
        record = formal_record_service.approve_formal_record(
            record_id=record_id,
            therapist_id=current_therapist.id,
        )
        db.commit()
        return FormalRecordResponse(
            record_id=record.id,
            rendered_text=record.rendered_text,
            record_json=record.record_json,
            record_type=record.record_type,
            status=record.status,
            approved_at=record.approved_at,
            model_used=record.model_used,
            tokens_used=record.tokens_used,
            created_at=record.created_at,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception(f"approve_formal_record record={record_id} failed: {e!r}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/patients/{patient_id}/formal-records", response_model=FormalRecordListResponse)
async def list_formal_records(
    patient_id: int,
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    current_therapist: Therapist = Depends(get_current_therapist),
    db: DBSession = Depends(get_db),
):
    """
    List formal records for a patient, newest first.
    Auth: therapist must own the patient.
    """
    formal_record_service = FormalRecordService(db)
    try:
        records, total = formal_record_service.list_formal_records(
            patient_id=patient_id,
            therapist_id=current_therapist.id,
            page=page,
            per_page=per_page,
        )
        return FormalRecordListResponse(
            records=[
                FormalRecordListItem(
                    record_id=r.id,
                    record_type=r.record_type,
                    status=r.status,
                    approved_at=r.approved_at,
                    created_at=r.created_at,
                )
                for r in records
            ],
            total=total,
            page=page,
            per_page=per_page,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"list_formal_records patient={patient_id} failed: {e!r}")
        raise HTTPException(status_code=500, detail=str(e))
