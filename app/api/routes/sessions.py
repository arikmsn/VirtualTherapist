"""Session management routes"""

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
from sqlalchemy.orm import Session as DBSession
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import date, datetime
from app.api.deps import get_db, get_current_therapist
from app.models.therapist import Therapist
from app.models.session import SessionType
from app.services.session_service import SessionService
from app.services.therapist_service import TherapistService
from loguru import logger

router = APIRouter()


# --- Request / Response models ---


class CreateSessionRequest(BaseModel):
    patient_id: int
    session_date: date
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    session_type: SessionType = SessionType.INDIVIDUAL
    duration_minutes: Optional[int] = None


class UpdateSessionRequest(BaseModel):
    session_date: Optional[date] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    session_type: Optional[SessionType] = None
    duration_minutes: Optional[int] = None


class SessionResponse(BaseModel):
    id: int
    therapist_id: int
    patient_id: int
    session_date: date
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    session_type: Optional[SessionType] = None
    duration_minutes: Optional[int] = None
    session_number: Optional[int] = None
    has_recording: bool
    summary_id: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


class DailySessionItem(BaseModel):
    id: int
    patient_id: int
    patient_name: str
    session_date: date
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    session_type: Optional[SessionType] = None
    session_number: Optional[int] = None
    has_summary: bool


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
    transcript: Optional[str] = None
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
            start_time=request.start_time,
            end_time=request.end_time,
        )
        return SessionResponse.model_validate(session)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"create_session therapist={current_therapist.id} failed: {e!r}")
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
        logger.exception(f"list_sessions therapist={current_therapist.id} failed: {e!r}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/by-date", response_model=List[DailySessionItem])
async def get_sessions_by_date(
    target_date: Optional[date] = Query(default=None, alias="date"),
    current_therapist: Therapist = Depends(get_current_therapist),
    db: DBSession = Depends(get_db),
):
    """Get sessions for a specific date (defaults to today)"""
    from datetime import date as date_type

    effective_date = target_date or date_type.today()
    service = SessionService(db)

    try:
        items = await service.get_sessions_by_date(
            therapist_id=current_therapist.id,
            target_date=effective_date,
        )
        return [DailySessionItem(**item) for item in items]

    except Exception as e:
        logger.exception(f"get_sessions_by_date therapist={current_therapist.id} date={effective_date} failed: {e!r}")
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
        logger.exception(f"get_patient_sessions patient={patient_id} failed: {e!r}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{session_id}", status_code=204)
async def delete_session(
    session_id: int,
    notify_patient: bool = Query(default=False, description="Log intent to notify patient of cancellation"),
    current_therapist: Therapist = Depends(get_current_therapist),
    db: DBSession = Depends(get_db),
):
    """
    Delete a session and its associated summary.
    notify_patient flag is accepted and logged; no message is sent yet.
    """
    from app.models.session import Session as SessionModel, SessionSummary
    from loguru import logger

    session = db.query(SessionModel).filter(
        SessionModel.id == session_id,
        SessionModel.therapist_id == current_therapist.id,
    ).first()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if notify_patient:
        logger.info(
            f"[session_delete] therapist={current_therapist.id} "
            f"session={session_id} patient={session.patient_id} "
            f"notify_patient=True - notification queued (not yet implemented)"
        )

    # sessions.summary_id → session_summaries.id  (FK is on sessions side)
    # Delete the session first to drop the FK reference, then delete the orphaned summary.
    summary_id = session.summary_id
    db.delete(session)
    db.flush()

    if summary_id:
        summary = db.query(SessionSummary).filter(SessionSummary.id == summary_id).first()
        if summary:
            db.delete(summary)

    db.commit()


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
        logger.exception(f"update_session session={session_id} failed: {e!r}")
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
        logger.exception(f"generate_summary_from_text session={session_id} RuntimeError: {e!r}")
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.exception(f"generate_summary_from_text session={session_id} failed: {e!r}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{session_id}/summary/from-audio", response_model=SummaryResponse)
async def generate_summary_from_audio(
    session_id: int,
    audio: UploadFile = File(...),
    language: Optional[str] = Form(default=None),
    current_therapist: Therapist = Depends(get_current_therapist),
    db: DBSession = Depends(get_db),
):
    """
    PRD Golden Path — Voice Recap:
    Upload audio → ASR transcription → AI structured summary.

    Accepts any audio format supported by Whisper (mp3, wav, m4a, ogg, webm).
    Language defaults to settings.DEFAULT_LANGUAGE (Hebrew) if not specified.
    """
    from app.core.config import settings as app_settings

    session_service = SessionService(db)
    therapist_service = TherapistService(db)

    # Read uploaded file
    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Empty audio file")

    max_size = app_settings.MAX_AUDIO_SIZE_MB * 1024 * 1024
    if len(audio_bytes) > max_size:
        raise HTTPException(
            status_code=413,
            detail=f"Audio file too large ({len(audio_bytes)} bytes). Max: {max_size} bytes.",
        )

    try:
        agent = await therapist_service.get_agent_for_therapist(current_therapist.id)
        summary = await session_service.generate_summary_from_audio(
            session_id=session_id,
            audio_bytes=audio_bytes,
            filename=audio.filename or "recording.webm",
            agent=agent,
            therapist_id=current_therapist.id,
            language=language,
        )
        return SummaryResponse.model_validate(summary)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        logger.exception(f"generate_summary_from_audio session={session_id} RuntimeError: {e!r}")
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.exception(f"generate_summary_from_audio session={session_id} failed: {e!r}")
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
        logger.exception(f"get_session_summary session={session_id} failed: {e!r}")
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
        logger.exception(f"patch_session_summary session={session_id} failed: {e!r}")
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
        logger.exception(f"approve_summary session={request.session_id} failed: {e!r}")
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
        logger.exception(f"edit_summary session={request.session_id} failed: {e!r}")
        raise HTTPException(status_code=500, detail=str(e))


class SessionPrepBriefResponse(BaseModel):
    quick_overview: str
    recent_progress: str
    key_points_to_revisit: List[str]
    watch_out_for: List[str]
    ideas_for_this_session: List[str]


@router.post("/{session_id}/prep-brief", response_model=SessionPrepBriefResponse)
async def generate_session_prep_brief(
    session_id: int,
    current_therapist: Therapist = Depends(get_current_therapist),
    db: DBSession = Depends(get_db),
):
    """Generate a concise AI prep brief for an upcoming session"""

    session_service = SessionService(db)
    therapist_service = TherapistService(db)

    try:
        agent = await therapist_service.get_agent_for_therapist(
            current_therapist.id,
        )

        result = await session_service.generate_prep_brief(
            session_id=session_id,
            therapist_id=current_therapist.id,
            agent=agent,
        )

        return SessionPrepBriefResponse(
            quick_overview=result.quick_overview,
            recent_progress=result.recent_progress,
            key_points_to_revisit=result.key_points_to_revisit,
            watch_out_for=result.watch_out_for,
            ideas_for_this_session=result.ideas_for_this_session,
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        logger.exception(f"generate_prep_brief session={session_id} RuntimeError: {e!r}")
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.exception(f"generate_prep_brief session={session_id} failed: {e!r}")
        raise HTTPException(status_code=500, detail=str(e))
