"""Patient management routes"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from datetime import date
from app.api.deps import get_db, get_current_therapist
from app.models.therapist import Therapist
from app.models.patient import PatientStatus
from app.services.patient_service import PatientService

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
    created_at: str

    class Config:
        from_attributes = True


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
        raise HTTPException(status_code=500, detail=str(e))
