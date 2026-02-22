"""Therapist profile routes — Twin v0.1 controls and profile management"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session as DBSession
from pydantic import BaseModel, Field
from typing import Optional, List
from app.api.deps import get_db, get_current_therapist
from app.models.therapist import Therapist
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

    class Config:
        from_attributes = True


class UpdateTwinControlsRequest(BaseModel):
    """Patch request for Twin v0.1 editable controls and professional info."""
    tone_warmth: Optional[int] = Field(default=None, ge=1, le=5)
    directiveness: Optional[int] = Field(default=None, ge=1, le=5)
    prohibitions: Optional[List[str]] = None
    custom_rules: Optional[str] = None
    # Professional credentials
    education: Optional[str] = None
    certifications: Optional[str] = None
    years_of_experience: Optional[str] = None
    areas_of_expertise: Optional[str] = None


# --- Helpers ---

def _profile_response(profile) -> TherapistProfileResponse:
    """Build a TherapistProfileResponse from an ORM TherapistProfile instance."""
    return TherapistProfileResponse(
        id=profile.id,
        therapist_id=profile.therapist_id,
        therapeutic_approach=profile.therapeutic_approach.value
            if profile.therapeutic_approach else "other",
        approach_description=profile.approach_description,
        tone=profile.tone,
        message_length_preference=profile.message_length_preference,
        common_terminology=profile.common_terminology,
        follow_up_frequency=profile.follow_up_frequency,
        preferred_exercises=profile.preferred_exercises,
        onboarding_completed=profile.onboarding_completed,
        onboarding_step=profile.onboarding_step,
        tone_warmth=profile.tone_warmth or 3,
        directiveness=profile.directiveness or 3,
        prohibitions=profile.prohibitions or [],
        custom_rules=profile.custom_rules,
        style_version=profile.style_version or 1,
        education=profile.education,
        certifications=profile.certifications,
        years_of_experience=profile.years_of_experience,
        areas_of_expertise=profile.areas_of_expertise,
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

    return _profile_response(profile)


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
        return _profile_response(profile)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception(f"update_twin_controls therapist={current_therapist.id} failed: {e!r}")
        raise HTTPException(status_code=500, detail=str(e))


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
        return _profile_response(profile)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception(f"reset_twin_controls therapist={current_therapist.id} failed: {e!r}")
        raise HTTPException(status_code=500, detail=str(e))
