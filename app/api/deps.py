"""API dependencies - database session, current user, etc."""

from typing import Generator
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.security.auth import decode_access_token
from app.models.therapist import Therapist
from app.services.therapist_service import TherapistService


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_db() -> Generator:
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def get_current_therapist(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> Therapist:
    """
    Get current authenticated therapist from JWT token

    Raises:
        HTTPException: If token is invalid or therapist not found
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # Decode token
    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception

    therapist_id: int = payload.get("sub")
    if therapist_id is None:
        raise credentials_exception

    # Get therapist
    therapist_service = TherapistService(db)
    therapist = therapist_service.get_therapist_by_id(therapist_id)

    if therapist is None:
        raise credentials_exception

    if not therapist.is_active:
        raise HTTPException(status_code=400, detail="Inactive therapist")

    return therapist


async def get_current_active_therapist(
    current_therapist: Therapist = Depends(get_current_therapist)
) -> Therapist:
    """Get current active therapist"""
    if not current_therapist.is_active:
        raise HTTPException(status_code=400, detail="Inactive therapist")
    return current_therapist
