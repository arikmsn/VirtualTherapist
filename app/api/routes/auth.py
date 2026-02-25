"""Authentication routes"""

from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from app.api.deps import get_db, get_current_therapist
from app.services.therapist_service import TherapistService
from app.security.auth import verify_password, create_access_token
from app.models.therapist import Therapist
from app.core.config import settings


router = APIRouter()


class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    therapist_id: int
    full_name: str
    email: str


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    phone: str | None = None


@router.post("/register", response_model=TokenResponse)
async def register(
    request: RegisterRequest,
    db: Session = Depends(get_db)
):
    """Register a new therapist account"""

    therapist_service = TherapistService(db)

    # Normalize therapist phone to E.164 if provided
    phone = request.phone
    if phone:
        from app.utils.phone import normalize_phone
        try:
            phone = normalize_phone(phone)
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    try:
        therapist = await therapist_service.create_therapist(
            email=request.email,
            password=request.password,
            full_name=request.full_name,
            phone=phone
        )

        # Create access token
        access_token = create_access_token(
            data={"sub": str(therapist.id)},
            expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        )

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "therapist_id": therapist.id,
            "full_name": therapist.full_name,
            "email": therapist.email,
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/login", response_model=TokenResponse)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """Login to get access token"""

    therapist_service = TherapistService(db)

    # Get therapist by email
    therapist = therapist_service.get_therapist_by_email(form_data.username)

    # Verify password
    if not therapist or not verify_password(form_data.password, therapist.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check if active
    if not therapist.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive account"
        )

    # Create access token
    access_token = create_access_token(
        data={"sub": str(therapist.id)},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "therapist_id": therapist.id,
        "full_name": therapist.full_name,
        "email": therapist.email,
    }


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    current_therapist: Therapist = Depends(get_current_therapist)
):
    """
    Silent token refresh.
    Accepts the current (non-expired) Bearer token, returns a fresh one.
    The frontend calls this proactively before the token expires.
    Returns 401 if the token is already expired — frontend handles logout.
    """
    new_token = create_access_token(
        data={"sub": str(current_therapist.id)},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    return {
        "access_token": new_token,
        "token_type": "bearer",
        "therapist_id": current_therapist.id,
        "full_name": current_therapist.full_name,
        "email": current_therapist.email,
    }
