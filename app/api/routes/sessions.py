"""Session management routes"""

import json
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session as DBSession
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import date, datetime
from app.api.deps import get_db, get_current_therapist
from app.api.errors import AIMeta
from app.models.therapist import Therapist
from app.models.session import SessionType
from app.services.precompute import (
    precompute_deep_summary_for_patient,
    precompute_treatment_plan_for_patient,
)
from app.services.session_service import SessionService
from app.services.therapist_service import TherapistService
from app.ai.prep import PrepMode
from loguru import logger

router = APIRouter()


def _require_session(db: "DBSession", session_id: int, therapist_id: int):
    """Load a session owned by *therapist_id* or raise HTTP 404."""
    from app.models.session import Session as _TherapySession
    session = db.query(_TherapySession).filter(
        _TherapySession.id == session_id,
        _TherapySession.therapist_id == therapist_id,
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


# --- Request / Response models ---


class CreateSessionRequest(BaseModel):
    patient_id: int
    session_date: date
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    session_type: SessionType = SessionType.INDIVIDUAL
    duration_minutes: Optional[int] = None
    notify_patient: bool = False  # send WhatsApp appointment reminder on creation


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
    summary_status: Optional[str] = None   # "draft" | "approved" | None (no summary)
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
    summary_status: Optional[str] = None   # "draft" | "approved" | None


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
    # AI generation metadata (Phase 1+)
    ai_model: Optional[str] = None
    modality_pack_id: Optional[int] = None
    # Completeness check results (Phase 2)
    completeness_score: Optional[float] = None
    completeness_data: Optional[Dict[str, Any]] = None
    # Session Summary 2.0 (Phase 3)
    clinical_json: Optional[Dict[str, Any]] = None
    # Edit lifecycle (Phase 9)
    edit_started_at: Optional[datetime] = None
    edit_ended_at: Optional[datetime] = None
    therapist_edit_count: Optional[int] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    # AI metadata block (Phase 9) — populated only on generate endpoints
    ai_meta: Optional[Dict[str, Any]] = None

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
            notify_patient=request.notify_patient,
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

        # Batch-load summary statuses in one query
        from app.models.session import SessionSummary as _SessionSummary
        summary_ids = [s.summary_id for s in sessions if s.summary_id]
        status_map: dict = {}
        if summary_ids:
            rows = db.query(
                _SessionSummary.id,
                _SessionSummary.status,
                _SessionSummary.approved_by_therapist,
            ).filter(_SessionSummary.id.in_(summary_ids)).all()
            for row in rows:
                status_map[row.id] = (
                    "approved" if row.approved_by_therapist else (row.status or "draft")
                )

        result = []
        for s in sessions:
            d = SessionResponse.model_validate(s).model_dump()
            d["summary_status"] = status_map.get(s.summary_id) if s.summary_id else None
            result.append(d)
        return result

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

        # Batch-load summary statuses in one query
        from app.models.session import SessionSummary as _SessionSummary
        summary_ids = [s.summary_id for s in sessions if s.summary_id]
        status_map: dict = {}
        if summary_ids:
            rows = db.query(
                _SessionSummary.id,
                _SessionSummary.status,
                _SessionSummary.approved_by_therapist,
            ).filter(_SessionSummary.id.in_(summary_ids)).all()
            for row in rows:
                status_map[row.id] = (
                    "approved" if row.approved_by_therapist else (row.status or "draft")
                )

        result = []
        for s in sessions:
            d = SessionResponse.model_validate(s).model_dump()
            d["summary_status"] = status_map.get(s.summary_id) if s.summary_id else None
            result.append(d)
        return result

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception(f"get_patient_sessions patient={patient_id} failed: {e!r}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{session_id}", status_code=204)
async def delete_session(
    session_id: int,
    background_tasks: BackgroundTasks,
    notify_patient: bool = Query(default=False, description="Log intent to notify patient of cancellation"),
    current_therapist: Therapist = Depends(get_current_therapist),
    db: DBSession = Depends(get_db),
):
    """
    Delete a session and its associated summary.
    notify_patient flag is accepted and logged; no message is sent yet.
    """
    service = SessionService(db)

    try:
        # Resolve patient_id before deleting (it's gone after deletion)
        from app.models.session import Session as _SessionModel
        _s = db.query(_SessionModel).filter(
            _SessionModel.id == session_id,
            _SessionModel.therapist_id == current_therapist.id,
        ).first()
        patient_id = _s.patient_id if _s else None

        if notify_patient and _s:
            logger.info(
                f"[session_delete] therapist={current_therapist.id} "
                f"session={session_id} patient={_s.patient_id} "
                f"notify_patient=True - notification queued (not yet implemented)"
            )

        await service.delete_session(session_id, current_therapist.id)

        # Session deletion changes the fingerprint → warm the caches
        if patient_id:
            background_tasks.add_task(
                precompute_deep_summary_for_patient,
                current_therapist.id,
                patient_id,
            )
            background_tasks.add_task(
                precompute_treatment_plan_for_patient,
                current_therapist.id,
                patient_id,
            )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


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


def _summary_response_with_meta(summary) -> SummaryResponse:
    """Build SummaryResponse and attach an AIMeta block from the summary's AI fields."""
    import dataclasses
    resp = SummaryResponse.model_validate(summary)
    if summary.ai_model:
        meta = AIMeta(
            model_used=summary.ai_model,
            tokens_used=0,           # token count not stored on SessionSummary
            generation_time_ms=0,    # latency not stored on SessionSummary
            completeness_score=summary.completeness_score,
            confidence=summary.ai_confidence,
            signature_applied=False,
        )
        resp.ai_meta = dataclasses.asdict(meta)
    return resp


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
        return _summary_response_with_meta(summary)

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
        return _summary_response_with_meta(summary)

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


@router.delete("/{session_id}/summary", status_code=204)
async def delete_session_summary(
    session_id: int,
    current_therapist: Therapist = Depends(get_current_therapist),
    db: DBSession = Depends(get_db),
):
    """
    Delete a session's AI-generated summary (keeps the session record).
    After deletion the session can receive a new summary via from-text or from-audio.
    """
    service = SessionService(db)
    try:
        await service.delete_session_summary(session_id, current_therapist.id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


class RegenerateFromTranscriptRequest(BaseModel):
    transcript: str


@router.post("/{session_id}/summary/regenerate-from-transcript", response_model=SummaryResponse)
async def regenerate_summary_from_transcript(
    session_id: int,
    request: RegenerateFromTranscriptRequest,
    current_therapist: Therapist = Depends(get_current_therapist),
    db: DBSession = Depends(get_db),
):
    """
    Regenerate an AI summary from a (potentially edited) transcript.

    The transcript is stored on the existing summary row and used as the input
    to generate a fresh AI summary. Returns the updated SummaryResponse.
    """
    session_service = SessionService(db)
    therapist_service = TherapistService(db)

    _require_session(db, session_id, current_therapist.id)

    if not request.transcript.strip():
        raise HTTPException(status_code=400, detail="Transcript cannot be empty")

    try:
        agent = await therapist_service.get_agent_for_therapist(current_therapist.id)
        summary = await session_service.generate_summary_from_text(
            session_id=session_id,
            therapist_notes=request.transcript,
            agent=agent,
            therapist_id=current_therapist.id,
        )
        # Persist the edited transcript on the summary so it's visible in the UI
        summary.transcript = request.transcript
        db.commit()
        return _summary_response_with_meta(summary)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        logger.exception(f"regenerate_from_transcript session={session_id} RuntimeError: {e!r}")
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.exception(f"regenerate_from_transcript session={session_id} failed: {e!r}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/summary/approve", response_model=SummaryResponse)
async def approve_summary(
    request: ApproveSummaryRequest,
    background_tasks: BackgroundTasks,
    current_therapist: Therapist = Depends(get_current_therapist),
    db: DBSession = Depends(get_db),
):
    """Approve an AI-generated session summary"""

    service = SessionService(db)

    try:
        # Resolve patient_id before approval so we can schedule background precompute
        from app.models.session import Session as _S
        _session = db.query(_S).filter(
            _S.id == request.session_id,
            _S.therapist_id == current_therapist.id,
        ).first()
        patient_id = _session.patient_id if _session else None

        summary = await service.approve_summary(
            session_id=request.session_id,
            therapist_id=current_therapist.id,
        )

        # Schedule best-effort cache warming for Deep Summary and Treatment Plan
        # after a new summary is approved (fingerprint of inputs has changed).
        if patient_id:
            logger.info(
                f"[approve_summary] scheduling precompute for "
                f"therapist={current_therapist.id} patient={patient_id}"
            )
            background_tasks.add_task(
                precompute_deep_summary_for_patient,
                current_therapist.id,
                patient_id,
            )
            background_tasks.add_task(
                precompute_treatment_plan_for_patient,
                current_therapist.id,
                patient_id,
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
    history_summary: List[str]    # מה היה עד עכשיו
    last_session: List[str]       # מה היה בפגישה האחרונה
    tasks_to_check: List[str]     # משימות לבדיקה היום
    focus_for_today: List[str]    # על מה כדאי להתמקד
    watch_out_for: List[str]      # שים לב


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
            history_summary=result.history_summary,
            last_session=result.last_session,
            tasks_to_check=result.tasks_to_check,
            focus_for_today=result.focus_for_today,
            watch_out_for=result.watch_out_for,
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        logger.exception(f"generate_prep_brief session={session_id} RuntimeError: {e!r}")
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.exception(f"generate_prep_brief session={session_id} failed: {e!r}")
        raise HTTPException(status_code=500, detail=str(e))


# ── Pre-Session Prep 2.0 (Phase 4) ─────────────────────────────────────────


class PrepRequest(BaseModel):
    mode: str = "concise"  # concise | deep | by_modality | gap_analysis


class PrepResponse(BaseModel):
    rendered_text: Optional[str] = None
    prep_json: Optional[Dict[str, Any]] = None
    mode: str
    completeness_score: Optional[float] = None
    sessions_analyzed: int = 0
    generated_at: Optional[str] = None


@router.get("/{session_id}/prep", response_model=PrepResponse)
async def get_stored_prep(
    session_id: int,
    current_therapist: Therapist = Depends(get_current_therapist),
    db: DBSession = Depends(get_db),
):
    """Return the stored prep brief for a session without regenerating."""
    from app.models.session import Session as _SessionModel
    session = db.query(_SessionModel).filter(
        _SessionModel.id == session_id,
        _SessionModel.therapist_id == current_therapist.id,
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return PrepResponse(
        rendered_text=session.prep_rendered_text,
        prep_json=session.prep_json,
        mode=session.prep_mode or "concise",
        sessions_analyzed=0,
        generated_at=str(session.prep_generated_at) if session.prep_generated_at else None,
    )


@router.post("/{session_id}/prep", response_model=PrepResponse)
async def generate_prep_v2(
    session_id: int,
    request: PrepRequest,
    current_therapist: Therapist = Depends(get_current_therapist),
    db: DBSession = Depends(get_db),
):
    """
    Generate a structured pre-session prep brief (Phase 4).

    Auth: therapist must own the session.
    Cache: returns cached result if same mode was generated within the last 10 minutes.
    Source of truth: only approved summaries (approved_by_therapist=True) are used.
    """
    try:
        mode = PrepMode(request.mode)
    except ValueError:
        valid = [m.value for m in PrepMode]
        raise HTTPException(
            status_code=422,
            detail=f"Invalid mode '{request.mode}'. Must be one of: {valid}",
        )

    session_service = SessionService(db)
    therapist_service = TherapistService(db)

    try:
        agent = await therapist_service.get_agent_for_therapist(current_therapist.id)
        result = await session_service.generate_prep_v2(
            session_id=session_id,
            therapist_id=current_therapist.id,
            mode=mode,
            agent=agent,
        )
        db.commit()
        return PrepResponse(**result)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        logger.exception(f"generate_prep_v2 session={session_id} RuntimeError: {e!r}")
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.exception(f"generate_prep_v2 session={session_id} failed: {e!r}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{session_id}/prep/stream")
async def stream_prep_v2(
    session_id: int,
    request: PrepRequest,
    current_therapist: Therapist = Depends(get_current_therapist),
    db: DBSession = Depends(get_db),
):
    """
    Streaming variant of POST /{session_id}/prep.

    SSE event stream:
      data: {"phase": "extracting"}          — extraction started (Call 1)
      data: {"phase": "rendering"}           — rendering started (Call 2, streaming)
      data: {"chunk": "..."}                 — rendered text fragment
      data: {"phase": "done", "prep_json": {...}, "sessions_analyzed": N}
      data: [DONE]                           — stream end sentinel

    The UI can display text progressively while Call 1 is still low-latency.
    """
    from app.ai.prep import PrepInput, PrepPipeline
    from app.ai.signature import SignatureEngine, inject_into_prompt

    mode_str = (request.mode or "concise").lower()
    try:
        mode = PrepMode(mode_str)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid prep mode: {mode_str}")

    session_service = SessionService(db)
    therapist_service = TherapistService(db)

    session = _require_session(db, session_id, current_therapist.id)

    agent = await therapist_service.get_agent_for_therapist(current_therapist.id)

    # ── Cache check (mirrors generate_prep_v2 logic) ──────────────────────────
    # If the same mode was generated recently, stream the cached text immediately
    # without calling the AI model.
    from datetime import datetime as _dt
    _PREP_CACHE_SECONDS = 600  # 10 minutes
    if (
        session.prep_json is not None
        and session.prep_mode == mode.value
        and session.prep_generated_at is not None
    ):
        _age = (_dt.utcnow() - session.prep_generated_at).total_seconds()
        _use_cache = False
        if _age < _PREP_CACHE_SECONDS:
            _use_cache = True
            logger.info(
                f"[stream_prep] session={session_id} mode={mode.value} — "
                f"time-based cache hit (age={_age:.0f}s)"
            )
        elif session.prep_input_fingerprint:
            # Outside time window — do fingerprint check
            from app.core.fingerprint import compute_fingerprint, FINGERPRINT_VERSION
            _fp_summaries = session_service._load_approved_summaries_for_prep(session.patient_id)
            _fp = compute_fingerprint({
                "mode": mode.value,
                "summaries": [
                    {
                        "summary_id": s.get("summary_id"),
                        "approved_at": s.get("approved_at"),
                        "full_summary": s["full_summary"],
                    }
                    for s in _fp_summaries
                ],
                "style_version": getattr(agent.profile, "style_version", 1) if agent.profile else 1,
            })
            if (
                _fp == session.prep_input_fingerprint
                and session.prep_input_fingerprint_version == FINGERPRINT_VERSION
            ):
                _use_cache = True
                logger.info(
                    f"[stream_prep] session={session_id} mode={mode.value} — "
                    f"fingerprint cache hit (inputs unchanged, age={_age:.0f}s)"
                )
        if _use_cache:
            cached_text = session.prep_rendered_text or ""

            async def _cached_sse():
                yield f"data: {json.dumps({'phase': 'rendering'})}\n\n"
                # Stream in chunks so the UI still sees progressive output
                chunk_size = 80
                for i in range(0, len(cached_text), chunk_size):
                    yield f"data: {json.dumps({'chunk': cached_text[i:i + chunk_size]})}\n\n"
                yield f"data: {json.dumps({'phase': 'done', 'prep_json': session.prep_json, 'sessions_analyzed': 0, 'cached': True})}\n\n"
                yield "data: [DONE]\n\n"

            return StreamingResponse(
                _cached_sse(),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
            )
    # ── End cache check ───────────────────────────────────────────────────────

    # Build approved summaries via service helper (joinedload, same logic as generate_prep_v2)
    approved_summaries = session_service._load_approved_summaries_for_prep(session.patient_id)

    modality_name = "generic_integrative"
    modality_prompt_module = None
    if agent.modality_pack:
        modality_name = agent.modality_pack.name
        modality_prompt_module = agent.modality_pack.prompt_module

    sig_engine = SignatureEngine(db)
    sig_profile = await sig_engine.get_active_profile(current_therapist.id)
    signature_prompt = inject_into_prompt(sig_profile) if sig_profile else None

    # AI protocol context
    from app.core.ai_context import build_ai_context_for_patient as _build_ai_ctx
    from app.models.patient import Patient as _Patient
    _patient_for_ctx = db.query(_Patient).filter(_Patient.id == session.patient_id).first()
    _ai_ctx = _build_ai_ctx(agent.profile if agent.profile else None, _patient_for_ctx, session_count=len(approved_summaries))

    prep_inp = PrepInput(
        client_id=session.patient_id,
        session_id=session_id,
        therapist_id=current_therapist.id,
        mode=mode,
        modality=modality_name,
        approved_summaries=approved_summaries,
        modality_prompt_module=modality_prompt_module,
        therapist_signature=signature_prompt,
        ai_context=_ai_ctx,
    )

    async def _sse_generator():
        pipeline = PrepPipeline(agent)
        full_text_chunks: list = []
        try:
            yield f"data: {json.dumps({'phase': 'extracting'})}\n\n"
            prep_json = await pipeline.extract_only(prep_inp)

            yield f"data: {json.dumps({'phase': 'rendering'})}\n\n"
            async for chunk in pipeline.render_stream(prep_inp, prep_json):
                full_text_chunks.append(chunk)
                yield f"data: {json.dumps({'chunk': chunk})}\n\n"

            yield f"data: {json.dumps({'phase': 'done', 'prep_json': prep_json, 'sessions_analyzed': len(approved_summaries)})}\n\n"
            yield "data: [DONE]\n\n"

            # Persist rendered text so subsequent requests hit the cache
            from datetime import datetime as _dt
            from app.core.fingerprint import compute_fingerprint, FINGERPRINT_VERSION
            session.prep_json = prep_json
            session.prep_mode = mode.value
            session.prep_rendered_text = "".join(full_text_chunks)
            session.prep_generated_at = _dt.utcnow()
            session.prep_input_fingerprint = compute_fingerprint({
                "mode": mode.value,
                "summaries": [
                    {
                        "summary_id": s.get("summary_id"),
                        "approved_at": s.get("approved_at"),
                        "full_summary": s.get("full_summary"),
                    }
                    for s in approved_summaries
                ],
                "style_version": getattr(agent.profile, "style_version", 1) if agent.profile else 1,
            })
            session.prep_input_fingerprint_version = FINGERPRINT_VERSION
            db.add(session)
            db.commit()
        except Exception as exc:
            logger.exception(f"stream_prep_v2 session={session_id} error: {exc!r}")
            yield f"data: {json.dumps({'error': str(exc)})}\n\n"

    return StreamingResponse(
        _sse_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── Multi-clip recording (Phase 10) ─────────────────────────────────────────


class ClipResponse(BaseModel):
    id: int
    clip_index: int
    duration_seconds: Optional[int] = None
    transcript: Optional[str] = None
    status: str
    created_at: datetime


@router.post(
    "/{session_id}/clips",
    response_model=ClipResponse,
    status_code=201,
)
async def upload_clip(
    session_id: int,
    audio: UploadFile = File(...),
    duration_seconds: Optional[int] = Form(default=None),
    language: Optional[str] = Form(default=None),
    current_therapist: Therapist = Depends(get_current_therapist),
    db: DBSession = Depends(get_db),
):
    """
    Upload a single audio clip for a session.

    Transcribes the clip immediately via Whisper and stores the result.
    Returns the clip with status='transcribed' and transcript text on success,
    or status='error' if transcription failed (allowing the UI to show a warning).
    """
    from app.models.audio_clip import AudioClip
    from app.services.audio_service import AudioService
    from app.core.config import settings as app_settings

    session = _require_session(db, session_id, current_therapist.id)

    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Empty audio file")

    max_size = app_settings.MAX_AUDIO_SIZE_MB * 1024 * 1024
    if len(audio_bytes) > max_size:
        raise HTTPException(
            status_code=413,
            detail=f"Audio file too large. Max: {app_settings.MAX_AUDIO_SIZE_MB} MB.",
        )

    # Determine clip index (next in sequence for this session)
    existing_count = db.query(AudioClip).filter(
        AudioClip.session_id == session_id,
    ).count()
    clip_index = existing_count + 1

    clip = AudioClip(
        session_id=session_id,
        therapist_id=current_therapist.id,
        clip_index=clip_index,
        duration_seconds=duration_seconds,
        status="pending",
    )
    db.add(clip)
    db.flush()  # get clip.id

    # Transcribe immediately
    try:
        audio_service = AudioService()
        transcript = await audio_service.transcribe_upload(
            file_bytes=audio_bytes,
            filename=audio.filename or f"clip_{clip_index}.webm",
            language=language,
        )
        clip.transcript = transcript
        clip.status = "transcribed"
    except Exception as exc:
        logger.warning(f"upload_clip session={session_id} clip={clip_index} transcription failed: {exc!r}")
        clip.status = "error"
        clip.error_message = str(exc)

    db.commit()
    db.refresh(clip)

    return ClipResponse(
        id=clip.id,
        clip_index=clip.clip_index,
        duration_seconds=clip.duration_seconds,
        transcript=clip.transcript,
        status=clip.status,
        created_at=clip.created_at,
    )


@router.get(
    "/{session_id}/clips",
    response_model=List[ClipResponse],
)
async def list_clips(
    session_id: int,
    current_therapist: Therapist = Depends(get_current_therapist),
    db: DBSession = Depends(get_db),
):
    """List all audio clips for a session, ordered by clip_index."""
    service = SessionService(db)
    try:
        clips = service.list_clips_for_session(session_id, current_therapist.id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return [
        ClipResponse(
            id=c.id,
            clip_index=c.clip_index,
            duration_seconds=c.duration_seconds,
            transcript=c.transcript,
            status=c.status,
            created_at=c.created_at,
        )
        for c in clips
    ]


@router.delete("/{session_id}/clips/{clip_id}", status_code=204)
async def delete_clip(
    session_id: int,
    clip_id: int,
    current_therapist: Therapist = Depends(get_current_therapist),
    db: DBSession = Depends(get_db),
):
    """Delete a single clip. Reorders remaining clips to fill the gap."""
    service = SessionService(db)
    try:
        service.delete_clip(clip_id, session_id, current_therapist.id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


class FinalizeClipsRequest(BaseModel):
    """Optional transcript override — when provided, skip merge and use this text directly."""
    transcript_override: Optional[str] = None


@router.post(
    "/{session_id}/clips/finalize",
    response_model=SummaryResponse,
    status_code=201,
)
async def finalize_clips(
    session_id: int,
    body: Optional[FinalizeClipsRequest] = None,
    current_therapist: Therapist = Depends(get_current_therapist),
    db: DBSession = Depends(get_db),
):
    """
    Merge all transcribed clip transcripts and generate a session summary.

    Clips are concatenated in clip_index order. Clips with status='error' are
    skipped (their absence noted in the merged transcript). Requires at least
    one transcribed clip.
    """
    from app.models.audio_clip import AudioClip

    _require_session(db, session_id, current_therapist.id)

    clips = (
        db.query(AudioClip)
        .filter(AudioClip.session_id == session_id)
        .order_by(AudioClip.clip_index.asc())
        .all()
    )

    if body and body.transcript_override:
        # Use the caller-supplied (possibly edited) transcript directly
        merged_transcript = body.transcript_override.strip()
    else:
        transcribed = [c for c in clips if c.status == "transcribed" and c.transcript]
        if not transcribed:
            raise HTTPException(
                status_code=400,
                detail="No transcribed clips found. Upload and transcribe clips first.",
            )

        # Merge: include a header per clip so the AI knows segment boundaries
        parts = []
        for c in transcribed:
            parts.append(f"[קטע {c.clip_index}]\n{c.transcript.strip()}")
        merged_transcript = "\n\n".join(parts)

    session_service = SessionService(db)
    therapist_service = TherapistService(db)

    try:
        agent = await therapist_service.get_agent_for_therapist(current_therapist.id)
        # Re-use the text summary path with the merged transcript as input notes
        summary = await session_service.generate_summary_from_text(
            session_id=session_id,
            therapist_notes=merged_transcript,
            agent=agent,
            therapist_id=current_therapist.id,
        )
        # Store the merged transcript on the summary for side-by-side display
        summary.transcript = merged_transcript
        summary.generated_from = "audio"
        db.commit()
        db.refresh(summary)
        return _summary_response_with_meta(summary)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        logger.exception(f"finalize_clips session={session_id} RuntimeError: {e!r}")
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.exception(f"finalize_clips session={session_id} failed: {e!r}")
        raise HTTPException(status_code=500, detail=str(e))
