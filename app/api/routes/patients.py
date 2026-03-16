"""Patient management routes"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from datetime import date, datetime
from app.api.deps import get_db, get_current_therapist
from app.models.therapist import Therapist
from app.models.patient import PatientStatus
from app.services.patient_service import PatientService
from app.services.session_service import SessionService
from app.services.therapist_service import TherapistService
from app.api.routes.sessions import SummaryResponse, PatientSummaryItem
from loguru import logger

router = APIRouter()


# --- Request / Response models ---


class CreatePatientRequest(BaseModel):
    full_name: str
    phone: Optional[str] = None
    email: Optional[str] = None
    start_date: Optional[date] = None
    primary_concerns: Optional[str] = None
    diagnosis: Optional[str] = None
    treatment_goals: Optional[List[str]] = None
    preferred_contact_time: Optional[str] = None
    allow_ai_contact: bool = True


class UpdatePatientRequest(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    status: Optional[PatientStatus] = None
    primary_concerns: Optional[str] = None
    diagnosis: Optional[str] = None
    treatment_goals: Optional[List[str]] = None
    next_session_date: Optional[date] = None
    allow_ai_contact: Optional[bool] = None
    preferred_contact_time: Optional[str] = None
    # Protocol library (migration 040) — list of protocol IDs active for this patient
    protocol_ids: Optional[List[str]] = None
    # Demographics placeholder (migration 040)
    demographics: Optional[dict] = None


class PatientResponse(BaseModel):
    id: int
    therapist_id: int
    full_name: str
    phone: Optional[str] = None
    email: Optional[str] = None
    status: PatientStatus
    start_date: Optional[date] = None
    allow_ai_contact: bool
    preferred_contact_time: Optional[str] = None
    completed_exercises_count: int
    missed_exercises_count: int
    created_at: datetime
    # Protocol library — non-encrypted, safe to expose
    protocol_ids: Optional[List[str]] = None

    class Config:
        from_attributes = True


class ProtocolProgressItem(BaseModel):
    id: str
    name: str
    current_stage: int
    typical_sessions: int


# --- Endpoints ---


@router.post("/", response_model=PatientResponse, status_code=201)
async def create_patient(
    request: CreatePatientRequest,
    current_therapist: Therapist = Depends(get_current_therapist),
    db: Session = Depends(get_db),
):
    """Create a new patient record (data encrypted at rest)"""

    service = PatientService(db)

    try:
        patient = await service.create_patient(
            therapist_id=current_therapist.id,
            full_name=request.full_name,
            phone=request.phone,
            email=request.email,
            start_date=request.start_date,
            primary_concerns=request.primary_concerns,
            diagnosis=request.diagnosis,
            treatment_goals=request.treatment_goals,
            preferred_contact_time=request.preferred_contact_time,
            allow_ai_contact=request.allow_ai_contact,
        )
        return PatientResponse.model_validate(patient)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"create_patient failed for therapist {current_therapist.id}: {e!r}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/", response_model=List[PatientResponse])
async def list_patients(
    status: Optional[PatientStatus] = Query(default=None),
    current_therapist: Therapist = Depends(get_current_therapist),
    db: Session = Depends(get_db),
):
    """List all patients for the current therapist"""

    service = PatientService(db)

    try:
        patients = await service.get_therapist_patients(
            therapist_id=current_therapist.id,
            status=status,
        )
        return [PatientResponse.model_validate(p) for p in patients]

    except Exception as e:
        logger.exception(f"list_patients failed for therapist {current_therapist.id}: {e!r}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{patient_id}", response_model=PatientResponse)
async def get_patient(
    patient_id: int,
    current_therapist: Therapist = Depends(get_current_therapist),
    db: Session = Depends(get_db),
):
    """Get a single patient by ID"""

    service = PatientService(db)

    patient = await service.get_patient(
        patient_id=patient_id,
        therapist_id=current_therapist.id,
    )

    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    return PatientResponse.model_validate(patient)


@router.put("/{patient_id}", response_model=PatientResponse)
async def update_patient(
    patient_id: int,
    request: UpdatePatientRequest,
    current_therapist: Therapist = Depends(get_current_therapist),
    db: Session = Depends(get_db),
):
    """Update a patient record"""

    service = PatientService(db)

    update_data = request.model_dump(exclude_unset=True)

    try:
        patient = await service.update_patient(
            patient_id=patient_id,
            therapist_id=current_therapist.id,
            update_data=update_data,
        )
        return PatientResponse.model_validate(patient)

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception(f"update_patient {patient_id} failed: {e!r}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{patient_id}")
async def delete_patient(
    patient_id: int,
    current_therapist: Therapist = Depends(get_current_therapist),
    db: Session = Depends(get_db),
):
    """Delete a patient and all related records"""

    service = PatientService(db)

    try:
        await service.delete_patient(
            patient_id=patient_id,
            therapist_id=current_therapist.id,
        )
        return {"message": "Patient deleted successfully"}

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception(f"delete_patient {patient_id} failed: {e!r}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{patient_id}/protocol-progress", response_model=List[ProtocolProgressItem])
async def get_protocol_progress(
    patient_id: int,
    current_therapist: Therapist = Depends(get_current_therapist),
    db: Session = Depends(get_db),
):
    """
    Return active protocol progress for this patient.

    Each item shows how many sessions the patient has had (current_stage)
    vs. the protocol's typical session count. Returns [] when no protocols
    are assigned to either the patient or the therapist.
    """
    from app.models.session import Session as TherapySession
    from app.models.therapist import TherapistProfile
    from app.core.protocol_context import build_protocol_context_for_patient

    service = PatientService(db)
    patient = await service.get_patient(patient_id=patient_id, therapist_id=current_therapist.id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    profile = (
        db.query(TherapistProfile)
        .filter(TherapistProfile.therapist_id == current_therapist.id)
        .first()
    )
    therapist_protocol_ids: List[str] = list(getattr(profile, "protocols_used", None) or [])
    custom_protocols: List[dict] = list(getattr(profile, "custom_protocols", None) or [])

    # patient.protocol_ids overrides therapist list when non-empty
    raw_patient_ids = getattr(patient, "protocol_ids", None) or []
    patient_protocol_ids = list(raw_patient_ids) if raw_patient_ids else None

    ctx = build_protocol_context_for_patient(
        therapist_protocol_ids=therapist_protocol_ids,
        therapist_custom_protocols=custom_protocols,
        patient_protocol_ids=patient_protocol_ids,
    )
    active_protocols = ctx.get("active_protocols", [])
    if not active_protocols:
        return []

    session_count: int = (
        db.query(func.count(TherapySession.id))
        .filter(
            TherapySession.patient_id == patient_id,
            TherapySession.therapist_id == current_therapist.id,
        )
        .scalar()
    ) or 0

    return [
        ProtocolProgressItem(
            id=p["id"],
            name=p["name"],
            current_stage=min(session_count, p.get("typical_sessions") or 12),
            typical_sessions=p.get("typical_sessions") or 12,
        )
        for p in active_protocols
    ]


@router.get("/{patient_id}/summaries", response_model=List[PatientSummaryItem])
async def get_patient_summaries(
    patient_id: int,
    current_therapist: Therapist = Depends(get_current_therapist),
    db: Session = Depends(get_db),
):
    """Get all session summaries for a patient"""

    service = SessionService(db)

    try:
        results = await service.get_patient_summaries(
            patient_id=patient_id,
            therapist_id=current_therapist.id,
        )
        return [
            PatientSummaryItem(
                session_id=r["session_id"],
                session_date=r["session_date"],
                session_number=r["session_number"],
                summary=SummaryResponse.model_validate(r["summary"]),
            )
            for r in results
        ]

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception(f"get_patient_summaries patient={patient_id} failed: {e!r}")
        raise HTTPException(status_code=500, detail=str(e))


class NoteCreate(BaseModel):
    content: str


class NoteResponse(BaseModel):
    id: int
    content: str
    created_at: datetime

    class Config:
        from_attributes = True


@router.get("/{patient_id}/notes", response_model=List[NoteResponse])
async def list_patient_notes(
    patient_id: int,
    current_therapist: Therapist = Depends(get_current_therapist),
    db: Session = Depends(get_db),
):
    """List therapist notebook notes for a patient (newest first)"""
    from app.models.patient import PatientNote
    from sqlalchemy import desc

    service = PatientService(db)
    patient = await service.get_patient(patient_id=patient_id, therapist_id=current_therapist.id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    notes = (
        db.query(PatientNote)
        .filter(PatientNote.patient_id == patient_id, PatientNote.therapist_id == current_therapist.id)
        .order_by(desc(PatientNote.created_at))
        .all()
    )
    return [NoteResponse.model_validate(n) for n in notes]


@router.post("/{patient_id}/notes", response_model=NoteResponse, status_code=201)
async def create_patient_note(
    patient_id: int,
    request: NoteCreate,
    current_therapist: Therapist = Depends(get_current_therapist),
    db: Session = Depends(get_db),
):
    """Create a therapist notebook note for a patient"""
    from app.models.patient import PatientNote

    service = PatientService(db)
    patient = await service.get_patient(patient_id=patient_id, therapist_id=current_therapist.id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    note = PatientNote(
        patient_id=patient_id,
        therapist_id=current_therapist.id,
        content=request.content,
    )
    db.add(note)
    db.commit()
    db.refresh(note)
    return NoteResponse.model_validate(note)


@router.delete("/{patient_id}/notes/{note_id}", status_code=200)
async def delete_patient_note(
    patient_id: int,
    note_id: int,
    current_therapist: Therapist = Depends(get_current_therapist),
    db: Session = Depends(get_db),
):
    """Delete a therapist notebook note"""
    from app.models.patient import PatientNote

    note = (
        db.query(PatientNote)
        .filter(
            PatientNote.id == note_id,
            PatientNote.patient_id == patient_id,
            PatientNote.therapist_id == current_therapist.id,
        )
        .first()
    )
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    db.delete(note)
    db.commit()
    return {"message": "Note deleted"}


class PatientInsightResponse(BaseModel):
    overview: str
    progress: str
    patterns: List[str]
    risks: List[str]
    suggestions_for_next_sessions: List[str]


class DeepSummaryResponse(BaseModel):
    """Structured deep summary — English keys, locale-appropriate text values."""
    overall_treatment_picture: str
    timeline_highlights: List[str]
    goals_and_tasks: str
    measurable_progress: str
    directions_for_next_phase: str


class TreatmentPlanGoal(BaseModel):
    id: str
    title: str
    description: str


class TreatmentPlanResponse(BaseModel):
    """Structured treatment plan preview — English keys, locale-appropriate text values."""
    goals: List[TreatmentPlanGoal]
    focus_areas: List[str]
    suggested_interventions: List[str]


@router.post("/{patient_id}/insight-summary", response_model=PatientInsightResponse)
async def generate_patient_insight_summary(
    patient_id: int,
    current_therapist: Therapist = Depends(get_current_therapist),
    db: Session = Depends(get_db),
):
    """Generate a cross-session AI insight report for a patient (therapist-only)"""

    session_service = SessionService(db)
    therapist_service = TherapistService(db)

    try:
        agent = await therapist_service.get_agent_for_therapist(
            current_therapist.id,
        )

        result = await session_service.generate_patient_insight(
            patient_id=patient_id,
            therapist_id=current_therapist.id,
            agent=agent,
        )

        return PatientInsightResponse(
            overview=result.overview,
            progress=result.progress,
            patterns=result.patterns,
            risks=result.risks,
            suggestions_for_next_sessions=result.suggestions_for_next_sessions,
        )

    except ValueError as e:
        logger.exception(f"generate_patient_insight patient={patient_id} ValueError: {e!r}")
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        logger.exception(f"generate_patient_insight patient={patient_id} RuntimeError: {e!r}")
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.exception(f"generate_patient_insight patient={patient_id} failed: {e!r}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{patient_id}/deep-summary", response_model=DeepSummaryResponse)
async def generate_deep_summary(
    patient_id: int,
    current_therapist: Therapist = Depends(get_current_therapist),
    db: Session = Depends(get_db),
):
    """
    Generate a comprehensive deep treatment summary from all approved session summaries and tasks.
    Returns structured JSON with English keys and locale-appropriate text values.
    """
    session_service = SessionService(db)
    therapist_service = TherapistService(db)

    try:
        agent = await therapist_service.get_agent_for_therapist(current_therapist.id)
        result = await session_service.generate_deep_summary(
            patient_id=patient_id,
            therapist_id=current_therapist.id,
            agent=agent,
        )

        # Persist to deep_summaries table so history can be retrieved
        from app.models.deep_summary import DeepSummary, DeepSummaryStatus
        summary_json = {
            "overall_treatment_picture": result.overall_treatment_picture,
            "timeline_highlights": result.timeline_highlights,
            "goals_and_tasks": result.goals_and_tasks,
            "measurable_progress": result.measurable_progress,
            "directions_for_next_phase": result.directions_for_next_phase,
        }
        rendered = "\n\n".join(filter(None, [
            result.overall_treatment_picture,
            result.goals_and_tasks,
            result.measurable_progress,
            result.directions_for_next_phase,
        ]))
        # Retrieve fingerprint computed inside generate_deep_summary (avoids re-querying)
        _fp_data = getattr(session_service, "_last_deep_summary_fingerprint", (None, None))
        db_row = DeepSummary(
            patient_id=patient_id,
            therapist_id=current_therapist.id,
            summary_json=summary_json,
            rendered_text=rendered or None,
            status=DeepSummaryStatus.APPROVED.value,
            input_fingerprint=_fp_data[0],
            input_fingerprint_version=_fp_data[1],
        )
        db.add(db_row)
        db.commit()

        return DeepSummaryResponse(
            overall_treatment_picture=result.overall_treatment_picture,
            timeline_highlights=result.timeline_highlights,
            goals_and_tasks=result.goals_and_tasks,
            measurable_progress=result.measurable_progress,
            directions_for_next_phase=result.directions_for_next_phase,
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        logger.exception(f"generate_deep_summary patient={patient_id} RuntimeError: {e!r}")
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.exception(f"generate_deep_summary patient={patient_id} failed: {e!r}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{patient_id}/treatment-plan/preview", response_model=TreatmentPlanResponse)
async def preview_treatment_plan(
    patient_id: int,
    current_therapist: Therapist = Depends(get_current_therapist),
    db: Session = Depends(get_db),
):
    """
    Generate a treatment plan preview (goals, focus areas, suggested interventions)
    inferred from approved session summaries and tasks.
    Returns structured JSON with English keys and locale-appropriate text values.
    """
    session_service = SessionService(db)
    therapist_service = TherapistService(db)

    try:
        agent = await therapist_service.get_agent_for_therapist(current_therapist.id)
        result = await session_service.generate_treatment_plan_preview(
            patient_id=patient_id,
            therapist_id=current_therapist.id,
            agent=agent,
        )
        return TreatmentPlanResponse(
            goals=[
                TreatmentPlanGoal(id=g.id, title=g.title, description=g.description)
                for g in result.goals
            ],
            focus_areas=result.focus_areas,
            suggested_interventions=result.suggested_interventions,
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        logger.exception(f"preview_treatment_plan patient={patient_id} RuntimeError: {e!r}")
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.exception(f"preview_treatment_plan patient={patient_id} failed: {e!r}")
        raise HTTPException(status_code=500, detail=str(e))
