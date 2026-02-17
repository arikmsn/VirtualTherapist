"""Session management routes"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session as DBSession
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import date, datetime
from app.api.deps import get_db, get_current_therapist
from app.models.therapist import Therapist
from app.models.session import SessionType
from app.services.session_service import SessionService
from app.services.therapist_service import TherapistService

router = APIRouter()


# --- Request / Response models ---


class CreateSessionRequest(BaseModel):
    patient_id: int
    session_date: date
    session_type: SessionType = SessionType.INDIVIDUAL
    duration_minutes: Optional[int] = None


class UpdateSessionRequest(BaseModel):
    session_date: Optional[date] = None
    session_type: Optional[SessionType] = None
    duration_minutes: Optional[int] = None


class SessionResponse(BaseModel):
    id: int
    therapist_id: int
    patient_id: int
    session_date: date
    session_type: Optional[SessionType] = None
    duration_minutes: Optional[int] = None
    session_number: Optional[int] = None
    has_recording: bool
    summary_id: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


class GenerateSummaryFromTextRequest(BaseModel):
    notes: str


class ApproveSummaryRequest(BaseModel):
    session_id: int


class EditSummaryRequest(BaseModel):
    session_id: int
    edited_content: Dict[str, Any]


class PatchSummaryRequest(BaseModel):
    full_summary: Optional[str] = None
    topics_discussed: Optional[List[str]] = None
    interventions_used: Optional[List[str]] = None
    patient_progress: Optional[str] = None
    homework_assigned: Optional[List[str]] = None
    next_session_plan: Optional[str] = None
    mood_observed: Optional[str] = None
    risk_assessment: Optional[str] = None
    status: Optional[str] = None  # "draft" or "approved"


class SummaryResponse(BaseModel):
    id: int
    full_summary: Optional[str] = None
    generated_from: Optional[str] = None
    therapist_edited: bool
    approved_by_therapist: bool
    status: Optional[str] = "draft"
    topics_discussed: Optional[List[str]] = None
    interventions_used: Optional[List[str]] = None
    patient_progress: Optional[str] = None
    homework_assigned: Optional[List[str]] = None
    next_session_plan: Optional[str] = None
    mood_observed: Optional[str] = None
    risk_assessment: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PatientSummaryItem(BaseModel):
    session_id: int
    session_date: date
    session_number: Optional[int] = None
    summary: SummaryResponse

    class Config:
        from_attributes = True


# --- CRUD endpoints ---


@router.post("/", response_model=SessionResponse, status_code=201)
async def create_session(
    request: CreateSessionRequest,
    current_therapist: Therapist = Depends(get_current_therapist),
    db: DBSession = Depends(get_db),
):
    """Create a new therapy session"""

    service = SessionService(db)

    try:
        session = await service.create_session(
            therapist_id=current_therapist.id,
            patient_id=request.patient_id,
            session_date=request.session_date,
            session_type=request.session_type,
            duration_minutes=request.duration_minutes,
        )
        return SessionResponse.model_validate(session)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/", response_model=List[SessionResponse])
async def list_sessions(
    limit: int = Query(default=50, le=200),
    current_therapist: Therapist = Depends(get_current_therapist),
    db: DBSession = Depends(get_db),
):
    """List recent sessions for the current therapist"""

    service = SessionService(db)

    try:
        sessions = await service.get_therapist_sessions(
            therapist_id=current_therapist.id,
            limit=limit,
        )
        return [SessionResponse.model_validate(s) for s in sessions]

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: int,
    current_therapist: Therapist = Depends(get_current_therapist),
    db: DBSession = Depends(get_db),
):
    """Get a single session by ID"""

    service = SessionService(db)

    session = await service.get_session(
        session_id=session_id,
        therapist_id=current_therapist.id,
    )

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return SessionResponse.model_validate(session)


@router.get(
    "/patient/{patient_id}",
    response_model=List[SessionResponse],
)
async def get_patient_sessions(
    patient_id: int,
    current_therapist: Therapist = Depends(get_current_therapist),
    db: DBSession = Depends(get_db),
):
    """Get all sessions for a specific patient"""

    service = SessionService(db)

    try:
        sessions = await service.get_patient_sessions(
            patient_id=patient_id,
            therapist_id=current_therapist.id,
        )
        return [SessionResponse.model_validate(s) for s in sessions]

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{session_id}", response_model=SessionResponse)
async def update_session(
    session_id: int,
    request: UpdateSessionRequest,
    current_therapist: Therapist = Depends(get_current_therapist),
    db: DBSession = Depends(get_db),
):
    """Update session details"""

    service = SessionService(db)
    update_data = request.model_dump(exclude_unset=True)

    try:
        session = await service.update_session(
            session_id=session_id,
            therapist_id=current_therapist.id,
            update_data=update_data,
        )
        return SessionResponse.model_validate(session)

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- Summary endpoints ---


@router.post("/{session_id}/summary/from-text", response_model=SummaryResponse)
async def generate_summary_from_text(
    session_id: int,
    request: GenerateSummaryFromTextRequest,
    current_therapist: Therapist = Depends(get_current_therapist),
    db: DBSession = Depends(get_db),
):
    """Generate a structured AI session summary from therapist text notes"""

    session_service = SessionService(db)
    therapist_service = TherapistService(db)

    try:
        agent = await therapist_service.get_agent_for_therapist(
            current_therapist.id,
        )

        summary = await session_service.generate_summary_from_text(
            session_id=session_id,
            therapist_notes=request.notes,
            agent=agent,
            therapist_id=current_therapist.id,
        )
        return SummaryResponse.model_validate(summary)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{session_id}/summary", response_model=SummaryResponse)
async def get_session_summary(
    session_id: int,
    current_therapist: Therapist = Depends(get_current_therapist),
    db: DBSession = Depends(get_db),
):
    """Get the AI-generated summary for a session"""

    service = SessionService(db)

    try:
        summary = await service.get_summary(
            session_id=session_id,
            therapist_id=current_therapist.id,
        )

        if not summary:
            raise HTTPException(status_code=404, detail="No summary found for this session")

        return SummaryResponse.model_validate(summary)

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{session_id}/summary", response_model=SummaryResponse)
async def patch_session_summary(
    session_id: int,
    request: PatchSummaryRequest,
    current_therapist: Therapist = Depends(get_current_therapist),
    db: DBSession = Depends(get_db),
):
    """Edit or approve a session summary (save draft / approve)"""

    service = SessionService(db)
    updates = request.model_dump(exclude_unset=True)

    try:
        summary = await service.update_summary(
            session_id=session_id,
            therapist_id=current_therapist.id,
            updates=updates,
        )
        return SummaryResponse.model_validate(summary)

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/summary/approve", response_model=SummaryResponse)
async def approve_summary(
    request: ApproveSummaryRequest,
    current_therapist: Therapist = Depends(get_current_therapist),
    db: DBSession = Depends(get_db),
):
    """Approve an AI-generated session summary"""

    service = SessionService(db)

    try:
        summary = await service.approve_summary(
            session_id=request.session_id,
            therapist_id=current_therapist.id,
        )
        return SummaryResponse.model_validate(summary)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/summary/edit", response_model=SummaryResponse)
async def edit_summary(
    request: EditSummaryRequest,
    current_therapist: Therapist = Depends(get_current_therapist),
    db: DBSession = Depends(get_db),
):
    """Edit an AI-generated session summary"""

    service = SessionService(db)

    try:
        summary = await service.edit_summary(
            session_id=request.session_id,
            therapist_id=current_therapist.id,
            edited_content=request.edited_content,
        )
        return SummaryResponse.model_validate(summary)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
