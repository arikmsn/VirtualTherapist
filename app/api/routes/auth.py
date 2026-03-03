"""Authentication routes"""

from datetime import timedelta, datetime, timezone
import secrets
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from app.api.deps import get_db, get_current_therapist
from app.services.therapist_service import TherapistService
from app.security.auth import verify_password, get_password_hash, create_access_token
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


# ---------------------------------------------------------------------------
# Google OAuth callback
# ---------------------------------------------------------------------------

class GoogleCallbackRequest(BaseModel):
    code: str
    redirect_uri: str


class GoogleTokenResponse(BaseModel):
    access_token: str
    token_type: str
    therapist_id: int
    full_name: str
    email: str
    is_onboarding_completed: bool


@router.post("/google/callback", response_model=GoogleTokenResponse)
async def google_callback(
    request: GoogleCallbackRequest,
    db: Session = Depends(get_db),
):
    """
    Exchange a Google authorization code for our JWT.

    Flow:
    1. Exchange code → Google tokens (using GOOGLE_CLIENT_ID + GOOGLE_CLIENT_SECRET).
    2. Verify the ID token with Google's public keys.
    3. Find-or-create the Therapist record (by google_sub, then email).
    4. Return our JWT + onboarding flag so the frontend can route appropriately.

    State / CSRF protection is handled on the frontend (checked before this call).
    """
    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google OAuth is not configured on this server",
        )

    # ── 1. Exchange authorization code for Google tokens ─────────────────
    import httpx
    async with httpx.AsyncClient() as client:
        token_response = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": request.code,
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "redirect_uri": request.redirect_uri,
                "grant_type": "authorization_code",
            },
        )

    token_data = token_response.json()
    if "error" in token_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Google token exchange failed: {token_data.get('error_description', token_data['error'])}",
        )

    id_token_str = token_data.get("id_token")
    if not id_token_str:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google did not return an ID token",
        )

    # ── 2. Verify the ID token ────────────────────────────────────────────
    try:
        from google.oauth2 import id_token as google_id_token
        from google.auth.transport import requests as google_requests
        id_info = google_id_token.verify_oauth2_token(
            id_token_str,
            google_requests.Request(),
            settings.GOOGLE_CLIENT_ID,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Google ID token verification failed: {exc}",
        )

    google_sub: str = id_info["sub"]
    email: str = id_info.get("email", "")
    email_verified: bool = id_info.get("email_verified", False)
    full_name: str = id_info.get("name", "") or ""

    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google account did not provide an email address",
        )

    # ── 3. Find or create therapist ───────────────────────────────────────
    therapist = db.query(Therapist).filter(Therapist.google_sub == google_sub).first()

    if therapist is None:
        # Try matching by email (existing local account → link Google)
        therapist = db.query(Therapist).filter(Therapist.email == email).first()
        if therapist is not None:
            # Link Google to existing account
            therapist.google_sub = google_sub
            if not therapist.auth_provider or therapist.auth_provider == "email":
                therapist.auth_provider = "google"
            db.commit()
            db.refresh(therapist)

    if therapist is None:
        # Brand-new user — create account with a random unusable password
        therapist = Therapist(
            email=email,
            hashed_password=get_password_hash(secrets.token_urlsafe(32)),
            full_name=full_name or email.split("@")[0],
            auth_provider="google",
            google_sub=google_sub,
            is_active=True,
            is_verified=email_verified,
        )
        db.add(therapist)
        db.commit()
        db.refresh(therapist)

    if not therapist.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This account has been deactivated",
        )

    # ── 4. Determine onboarding status ───────────────────────────────────
    onboarding_completed = bool(
        therapist.profile and therapist.profile.onboarding_completed
    )

    # ── 5. Issue JWT ──────────────────────────────────────────────────────
    access_token = create_access_token(
        data={"sub": str(therapist.id)},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "therapist_id": therapist.id,
        "full_name": therapist.full_name,
        "email": therapist.email,
        "is_onboarding_completed": onboarding_completed,
    }
