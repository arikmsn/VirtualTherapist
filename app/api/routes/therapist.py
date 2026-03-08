"""Therapist profile routes — Twin v0.1 controls and profile management"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session as DBSession
from sqlalchemy import desc
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from app.api.deps import get_db, get_current_therapist
from app.models.therapist import Therapist, TherapistNote
from app.services.therapist_service import TherapistService
from loguru import logger

router = APIRouter()


# --- Schemas ---

class TherapistProfileResponse(BaseModel):
    """Full therapist profile, including Twin v0.1 controls and professional info."""
    id: int
    therapist_id: int
    therapeutic_approach: str
    approach_description: Optional[str] = None
    tone: Optional[str] = None
    message_length_preference: Optional[str] = None
    common_terminology: Optional[List[str]] = None
    follow_up_frequency: Optional[str] = None
    preferred_exercises: Optional[List[str]] = None
    onboarding_completed: bool
    onboarding_step: int
    # Twin controls
    tone_warmth: int = Field(default=3, ge=1, le=5)
    directiveness: int = Field(default=3, ge=1, le=5)
    prohibitions: Optional[List[str]] = None
    custom_rules: Optional[str] = None
    style_version: int = 1
    # Professional credentials
    education: Optional[str] = None
    certifications: Optional[str] = None
    years_of_experience: Optional[str] = None
    areas_of_expertise: Optional[str] = None
    # Therapist account creation date (used for "days since signup" display)
    therapist_created_at: Optional[datetime] = None
    # Derived: True when CBT is active for this therapist (drives UI hints)
    cbt_active: bool = False
    # Profession + therapy modes (migration 029)
    profession: Optional[str] = None
    primary_therapy_modes: Optional[List[str]] = None

    class Config:
        from_attributes = True


class UpdateTwinControlsRequest(BaseModel):
    """Patch request for Twin v0.1 editable controls and professional info."""
    tone_warmth: Optional[int] = Field(default=None, ge=1, le=5)
    directiveness: Optional[int] = Field(default=None, ge=1, le=5)
    prohibitions: Optional[List[str]] = None
    custom_rules: Optional[str] = None
    # Onboarding-collected style field — now editable from Twin profile page
    tone: Optional[str] = None
    # Therapeutic modalities (stored as comma-separated values in approach_description)
    approach_description: Optional[str] = None
    # Professional credentials
    education: Optional[str] = None
    certifications: Optional[str] = None
    years_of_experience: Optional[str] = None
    areas_of_expertise: Optional[str] = None
    # Profession + therapy modes (migration 029)
    profession: Optional[str] = None
    primary_therapy_modes: Optional[List[str]] = None


# --- Helpers ---

VALID_THERAPY_MODES = [
    "cbt", "psychodynamic", "act", "dbt", "humanistic",
    "family_systemic", "integrative", "emdr", "gestalt", "psychodrama", "other",
]


def _derive_modes(profile) -> List[str]:
    """
    Derive a therapy-modes list from legacy fields when primary_therapy_modes is absent.

    Priority:
    1. profile.primary_therapy_modes — non-empty JSON list (migration 029)
    2. profile.approach_description  — CSV string e.g. "CBT, psychodynamic"
    3. profile.therapeutic_approach  — single enum value
    4. []                             — no information
    """
    if profile.primary_therapy_modes and isinstance(profile.primary_therapy_modes, list):
        return profile.primary_therapy_modes

    modes: list[str] = []
    if profile.approach_description:
        for raw in profile.approach_description.split(","):
            v = raw.strip().lower()
            if v in VALID_THERAPY_MODES:
                modes.append(v)
            elif raw.strip().upper() == "CBT":
                modes.append("cbt")
            elif raw.strip().upper() == "DBT":
                modes.append("dbt")
            elif raw.strip().upper() == "ACT":
                modes.append("act")
            elif raw.strip().upper() == "EMDR":
                modes.append("emdr")
    if not modes and profile.therapeutic_approach:
        v = str(profile.therapeutic_approach).lower()
        if v in VALID_THERAPY_MODES:
            modes.append(v)
    return modes


def _to_list(v):
    """Return v if it's already a list, else None.

    Guards against empty-string values that SQLite/JSON columns may
    occasionally store when submitted via a form — Pydantic List[str]
    validation rejects '' with a list_type error.
    """
    return v if isinstance(v, list) else None


def _profile_response(profile, therapist=None) -> TherapistProfileResponse:
    """Build a TherapistProfileResponse from an ORM TherapistProfile instance."""
    from app.ai.modality import is_cbt_active
    return TherapistProfileResponse(
        id=profile.id,
        therapist_id=profile.therapist_id,
        therapeutic_approach=profile.therapeutic_approach.value
            if profile.therapeutic_approach else "other",
        approach_description=profile.approach_description,
        tone=profile.tone,
        message_length_preference=profile.message_length_preference,
        common_terminology=_to_list(profile.common_terminology),
        follow_up_frequency=profile.follow_up_frequency,
        preferred_exercises=_to_list(profile.preferred_exercises),
        onboarding_completed=profile.onboarding_completed,
        onboarding_step=profile.onboarding_step,
        tone_warmth=profile.tone_warmth or 3,
        directiveness=profile.directiveness or 3,
        prohibitions=_to_list(profile.prohibitions) or [],
        custom_rules=profile.custom_rules,
        style_version=profile.style_version or 1,
        education=profile.education,
        certifications=profile.certifications,
        years_of_experience=profile.years_of_experience,
        areas_of_expertise=profile.areas_of_expertise,
        therapist_created_at=therapist.created_at if therapist else None,
        cbt_active=is_cbt_active(profile),
        profession=profile.profession,
        primary_therapy_modes=_derive_modes(profile),
    )


# --- Endpoints ---

@router.get("/profile", response_model=TherapistProfileResponse)
async def get_therapist_profile(
    current_therapist: Therapist = Depends(get_current_therapist),
    db: DBSession = Depends(get_db),
):
    """Return the current therapist's full profile including Twin controls."""
    profile = current_therapist.profile
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    return _profile_response(profile, therapist=current_therapist)


@router.patch("/profile", response_model=TherapistProfileResponse)
async def update_twin_controls(
    request: UpdateTwinControlsRequest,
    current_therapist: Therapist = Depends(get_current_therapist),
    db: DBSession = Depends(get_db),
):
    """
    Update Twin v0.1 editable controls (tone warmth, directiveness,
    prohibitions, custom rules). Increments style_version on save.
    These changes take effect immediately on all subsequent AI calls.
    """
    service = TherapistService(db)

    updates = request.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    # Bump style version whenever the therapist saves changes
    updates["style_version"] = (current_therapist.profile.style_version or 1) + 1

    try:
        profile = await service.update_profile(
            therapist_id=current_therapist.id,
            profile_data=updates,
        )
        return _profile_response(profile, therapist=current_therapist)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception(f"update_twin_controls therapist={current_therapist.id} failed: {e!r}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/profile/complete-onboarding", status_code=200)
async def complete_onboarding(
    current_therapist: Therapist = Depends(get_current_therapist),
    db: DBSession = Depends(get_db),
):
    """
    Mark onboarding as complete for the current therapist.
    Called at the end of the onboarding wizard flow.
    Idempotent — safe to call multiple times.
    """
    profile = current_therapist.profile
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    if not profile.onboarding_completed:
        profile.onboarding_completed = True
        db.commit()

    return {"onboarding_completed": True}


@router.post("/profile/reset", response_model=TherapistProfileResponse)
async def reset_twin_controls(
    current_therapist: Therapist = Depends(get_current_therapist),
    db: DBSession = Depends(get_db),
):
    """
    Reset Twin controls to neutral defaults.
    Clears prohibitions, custom rules, and resets sliders to midpoint (3).
    Bumps style_version.
    """
    service = TherapistService(db)

    updates = {
        "tone_warmth": 3,
        "directiveness": 3,
        "prohibitions": [],
        "custom_rules": None,
        "style_version": (current_therapist.profile.style_version or 1) + 1,
    }

    try:
        profile = await service.update_profile(
            therapist_id=current_therapist.id,
            profile_data=updates,
        )
        return _profile_response(profile, therapist=current_therapist)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception(f"reset_twin_controls therapist={current_therapist.id} failed: {e!r}")
        raise HTTPException(status_code=500, detail=str(e))


# ── Side Notebook ─────────────────────────────────────────────────────────────


class SideNoteCreate(BaseModel):
    title: Optional[str] = None
    content: str
    tags: Optional[List[str]] = None


class SideNoteUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    tags: Optional[List[str]] = None


class SideNoteResponse(BaseModel):
    id: int
    title: Optional[str] = None
    content: str
    tags: Optional[List[str]] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


@router.get("/notes", response_model=List[SideNoteResponse])
async def list_side_notes(
    current_therapist: Therapist = Depends(get_current_therapist),
    db: DBSession = Depends(get_db),
):
    """List all side-notebook notes for the current therapist (newest first)."""
    notes = (
        db.query(TherapistNote)
        .filter(TherapistNote.therapist_id == current_therapist.id)
        .order_by(desc(TherapistNote.created_at))
        .all()
    )
    return [SideNoteResponse.model_validate(n) for n in notes]


@router.post("/notes", response_model=SideNoteResponse, status_code=201)
async def create_side_note(
    request: SideNoteCreate,
    current_therapist: Therapist = Depends(get_current_therapist),
    db: DBSession = Depends(get_db),
):
    """Create a new side-notebook note."""
    note = TherapistNote(
        therapist_id=current_therapist.id,
        title=request.title,
        content=request.content,
        tags=request.tags,
    )
    db.add(note)
    db.commit()
    db.refresh(note)
    return SideNoteResponse.model_validate(note)


@router.patch("/notes/{note_id}", response_model=SideNoteResponse)
async def update_side_note(
    note_id: int,
    request: SideNoteUpdate,
    current_therapist: Therapist = Depends(get_current_therapist),
    db: DBSession = Depends(get_db),
):
    """Update an existing side-notebook note."""
    note = (
        db.query(TherapistNote)
        .filter(TherapistNote.id == note_id, TherapistNote.therapist_id == current_therapist.id)
        .first()
    )
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")

    if request.title is not None:
        note.title = request.title
    if request.content is not None:
        note.content = request.content
    if request.tags is not None:
        note.tags = request.tags

    db.commit()
    db.refresh(note)
    return SideNoteResponse.model_validate(note)


# ── Today Insights ────────────────────────────────────────────────────────────


class TodayInsightItemResponse(BaseModel):
    patient_id: int
    title: str
    body: str


class TodayInsightsResponse(BaseModel):
    insights: List[TodayInsightItemResponse]


@router.get("/today-insights", response_model=TodayInsightsResponse)
async def get_today_insights(
    current_therapist: Therapist = Depends(get_current_therapist),
    db: DBSession = Depends(get_db),
):
    """
    Generate AI smart reminders for today's sessions.
    Returns {"insights": [{patient_id, title, body}]}.
    On any error (including AI failure) returns {"insights": []} — never blocks the caller.
    """
    from datetime import date as date_cls
    from sqlalchemy import asc
    from app.models.session import Session as TherapySession, SessionSummary, SummaryStatus
    from app.models.patient import Patient
    from app.models.exercise import Exercise
    from app.security.encryption import decrypt_data

    today = date_cls.today()

    try:
        # 1. Today's sessions for this therapist
        today_sessions = (
            db.query(TherapySession)
            .filter(
                TherapySession.therapist_id == current_therapist.id,
                TherapySession.session_date == today,
            )
            .all()
        )

        if not today_sessions:
            return TodayInsightsResponse(insights=[])

        # 2. Resolve patients (deduplicated)
        patient_ids = list({s.patient_id for s in today_sessions})
        patients_map: dict = {
            p.id: p
            for p in db.query(Patient).filter(Patient.id.in_(patient_ids)).all()
        }

        # 3. Build per-patient context
        patients_context = []
        for session in today_sessions:
            pid = session.patient_id
            patient = patients_map.get(pid)
            if not patient:
                continue

            # Decrypt patient name
            patient_name = (
                decrypt_data(patient.full_name_encrypted)
                if patient.full_name_encrypted
                else "מטופל"
            )

            # Last 2 approved summaries for this patient (newest first)
            patient_session_ids_q = (
                db.query(TherapySession.id, TherapySession.session_date, TherapySession.session_number)
                .filter(
                    TherapySession.patient_id == pid,
                    TherapySession.therapist_id == current_therapist.id,
                )
                .order_by(TherapySession.session_date.desc())
                .limit(10)
                .all()
            )
            session_id_list = [r[0] for r in patient_session_ids_q]
            session_info_map = {r[0]: {"session_date": r[1], "session_number": r[2]} for r in patient_session_ids_q}

            approved_summaries = []
            if session_id_list:
                summaries_raw = (
                    db.query(SessionSummary)
                    .filter(
                        SessionSummary.session_id.in_(session_id_list),
                        SessionSummary.status == SummaryStatus.APPROVED,
                    )
                    .all()
                )
                # Sort newest first via session_info_map
                summaries_sorted = sorted(
                    summaries_raw,
                    key=lambda ss: session_info_map.get(ss.session_id, {}).get("session_date", today),
                    reverse=True,
                )
                for ss in summaries_sorted[:2]:
                    info = session_info_map.get(ss.session_id, {})
                    approved_summaries.append({
                        "session_date": str(info.get("session_date", "?")),
                        "session_number": info.get("session_number"),
                        "full_summary": ss.full_summary or "",
                        "topics_discussed": ss.topics_discussed or [],
                        "patient_progress": ss.patient_progress or "",
                    })

            # Open tasks for this patient
            open_tasks_raw = (
                db.query(Exercise)
                .filter(
                    Exercise.patient_id == pid,
                    Exercise.therapist_id == current_therapist.id,
                    Exercise.completed == False,  # noqa: E712
                )
                .all()
            )
            open_tasks = [{"description": t.description} for t in open_tasks_raw]

            patients_context.append({
                "patient_id": pid,
                "patient_name": patient_name,
                "session_number": session.session_number,
                "approved_summaries": approved_summaries,
                "open_tasks": open_tasks,
            })

        if not patients_context:
            return TodayInsightsResponse(insights=[])

        # 4. One AI call for all patients
        therapist_service = TherapistService(db)
        agent = await therapist_service.get_agent_for_therapist(current_therapist.id)

        therapist_locale = (
            (agent.profile.language if agent.profile else None) or "he"
        )

        result = await agent.generate_today_insights(
            patients_context=patients_context,
            therapist_locale=therapist_locale,
        )

        return TodayInsightsResponse(
            insights=[
                TodayInsightItemResponse(
                    patient_id=item.patient_id,
                    title=item.title,
                    body=item.body,
                )
                for item in result.insights
            ]
        )

    except Exception as e:
        logger.exception(f"get_today_insights therapist={current_therapist.id} failed: {e!r}")
        # Non-blocking: return empty rather than surfacing an error
        return TodayInsightsResponse(insights=[])


@router.delete("/notes/{note_id}", status_code=200)
async def delete_side_note(
    note_id: int,
    current_therapist: Therapist = Depends(get_current_therapist),
    db: DBSession = Depends(get_db),
):
    """Delete a side-notebook note."""
    note = (
        db.query(TherapistNote)
        .filter(TherapistNote.id == note_id, TherapistNote.therapist_id == current_therapist.id)
        .first()
    )
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    db.delete(note)
    db.commit()
    return {"message": "Note deleted"}


# ── Signature Profile (Phase 6) ──────────────────────────────────────────────


class SignatureProfileResponse(BaseModel):
    is_active: bool
    approved_sample_count: int
    min_samples_required: int
    samples_until_active: int
    style_summary: Optional[str] = None
    style_version: int
    last_updated_at: Optional[datetime] = None


@router.get("/signature-profile", response_model=SignatureProfileResponse)
async def get_signature_profile(
    current_therapist: Therapist = Depends(get_current_therapist),
    db: DBSession = Depends(get_db),
):
    """
    Return the current therapist signature profile status.
    Includes sample count, activation threshold, and learned style summary.
    """
    from app.ai.signature import SignatureEngine
    from app.models.signature import TherapistSignatureProfile
    from app.models.session import SessionSummary as _SessionSummary, Session as _TherapySession

    row = (
        db.query(TherapistSignatureProfile)
        .filter(TherapistSignatureProfile.therapist_id == current_therapist.id)
        .first()
    )
    # Always use a live query for the approved summary count.
    # The engine's internal counter (row.approved_sample_count) lags behind because
    # record_approval() is only triggered when ai_draft_text is set and the async
    # task completes.  The DB field `is_active` is only set to True during an AI
    # rebuild (provider != None), which never runs in the approval hot-path.
    # Therefore we derive both count and is_active from the live query.
    count = (
        db.query(_SessionSummary)
        .join(_TherapySession, _TherapySession.summary_id == _SessionSummary.id)
        .filter(
            _TherapySession.therapist_id == current_therapist.id,
            _SessionSummary.approved_by_therapist == True,
        )
        .count()
    )
    min_req = row.min_samples_required if row else 5
    is_active_live = count >= min_req   # derived from fresh count, not stale DB field
    return SignatureProfileResponse(
        is_active=is_active_live,
        approved_sample_count=count,
        min_samples_required=min_req,
        samples_until_active=max(0, min_req - count),
        style_summary=row.style_summary if row else None,
        style_version=row.style_version if row else 1,
        last_updated_at=row.last_updated_at if row else None,
    )


@router.delete("/signature-profile", status_code=200)
async def reset_signature_profile(
    current_therapist: Therapist = Depends(get_current_therapist),
    db: DBSession = Depends(get_db),
):
    """
    Reset the therapist's learned signature profile.
    Clears raw_samples, sets is_active=False, resets approved_sample_count to 0.
    The therapist can start fresh if they don't like the learned style.
    """
    from app.ai.signature import SignatureEngine

    engine = SignatureEngine(db)
    engine.reset_profile(current_therapist.id)
    db.commit()
    return {"message": "Signature profile reset successfully"}
