"""Exercise / homework management routes."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session as DBSession
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from app.api.deps import get_db, get_current_therapist
from app.models.therapist import Therapist
from app.models.exercise import Exercise
from app.models.patient import Patient

router = APIRouter()


# ── Schemas ──────────────────────────────────────────────────────────────────

class ExerciseResponse(BaseModel):
    id: int
    patient_id: int
    therapist_id: int
    session_summary_id: Optional[int] = None
    description: str
    completed: bool
    completed_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class CreateExerciseRequest(BaseModel):
    patient_id: int
    description: str
    session_summary_id: Optional[int] = None


class PatchExerciseRequest(BaseModel):
    completed: Optional[bool] = None
    description: Optional[str] = None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _sync_completed_count(patient_id: int, db: DBSession) -> None:
    """Recompute and persist patient.completed_exercises_count."""
    count = db.query(Exercise).filter(
        Exercise.patient_id == patient_id,
        Exercise.completed == True,  # noqa: E712
    ).count()
    db.query(Patient).filter(Patient.id == patient_id).update(
        {"completed_exercises_count": count}
    )
    db.flush()


def _owned_exercise(exercise_id: int, therapist_id: int, db: DBSession) -> Exercise:
    ex = db.query(Exercise).filter(
        Exercise.id == exercise_id,
        Exercise.therapist_id == therapist_id,
    ).first()
    if not ex:
        raise HTTPException(status_code=404, detail="Exercise not found")
    return ex


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/", response_model=List[ExerciseResponse])
async def list_exercises(
    patient_id: int = Query(...),
    current_therapist: Therapist = Depends(get_current_therapist),
    db: DBSession = Depends(get_db),
):
    """List all exercises for a patient (owned by current therapist)."""
    # Verify patient belongs to therapist
    patient = db.query(Patient).filter(
        Patient.id == patient_id,
        Patient.therapist_id == current_therapist.id,
    ).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    exercises = (
        db.query(Exercise)
        .filter(Exercise.patient_id == patient_id, Exercise.therapist_id == current_therapist.id)
        .order_by(Exercise.created_at.desc())
        .all()
    )
    return [ExerciseResponse.model_validate(e) for e in exercises]


@router.post("/", response_model=ExerciseResponse, status_code=201)
async def create_exercise(
    request: CreateExerciseRequest,
    current_therapist: Therapist = Depends(get_current_therapist),
    db: DBSession = Depends(get_db),
):
    """Create a new exercise for a patient."""
    patient = db.query(Patient).filter(
        Patient.id == request.patient_id,
        Patient.therapist_id == current_therapist.id,
    ).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    ex = Exercise(
        patient_id=request.patient_id,
        therapist_id=current_therapist.id,
        session_summary_id=request.session_summary_id,
        description=request.description,
        completed=False,
    )
    db.add(ex)
    db.commit()
    db.refresh(ex)
    return ExerciseResponse.model_validate(ex)


@router.patch("/{exercise_id}", response_model=ExerciseResponse)
async def patch_exercise(
    exercise_id: int,
    request: PatchExerciseRequest,
    current_therapist: Therapist = Depends(get_current_therapist),
    db: DBSession = Depends(get_db),
):
    """Toggle completion or update description of an exercise."""
    ex = _owned_exercise(exercise_id, current_therapist.id, db)

    if request.description is not None:
        ex.description = request.description

    if request.completed is not None:
        ex.completed = request.completed
        ex.completed_at = datetime.utcnow() if request.completed else None

    db.commit()
    db.refresh(ex)

    # Keep patient counter in sync
    _sync_completed_count(ex.patient_id, db)
    db.commit()

    return ExerciseResponse.model_validate(ex)


@router.get("/open-count")
async def get_open_tasks_count(
    current_therapist: Therapist = Depends(get_current_therapist),
    db: DBSession = Depends(get_db),
):
    """Return the count of incomplete exercises across all patients for this therapist."""
    count = db.query(Exercise).filter(
        Exercise.therapist_id == current_therapist.id,
        Exercise.completed == False,  # noqa: E712
    ).count()
    return {"open_count": count}


@router.delete("/{exercise_id}", status_code=204)
async def delete_exercise(
    exercise_id: int,
    current_therapist: Therapist = Depends(get_current_therapist),
    db: DBSession = Depends(get_db),
):
    """Delete an exercise."""
    ex = _owned_exercise(exercise_id, current_therapist.id, db)
    patient_id = ex.patient_id
    db.delete(ex)
    db.commit()
    _sync_completed_count(patient_id, db)
    db.commit()
