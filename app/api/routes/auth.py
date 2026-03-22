"""Authentication routes"""

from datetime import timedelta, datetime, timezone
import hashlib
import hmac
import secrets
import time
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from typing import Optional
from pydantic import BaseModel, EmailStr
from app.api.deps import get_db, get_current_therapist
from app.services.therapist_service import TherapistService
from app.security.auth import verify_password, get_password_hash, create_access_token
from app.models.therapist import Therapist, TherapistProfile, TherapeuticApproach
from app.models.admin_alert import AdminAlert
from app.core.config import settings


# ---------------------------------------------------------------------------
# HMAC-signed OAuth state helpers (CSRF protection)
# ---------------------------------------------------------------------------

def _sign_state(raw: str) -> str:
    """Return HMAC-SHA256 hex signature of raw using SECRET_KEY."""
    key = settings.SECRET_KEY.encode()
    return hmac.new(key, raw.encode(), hashlib.sha256).hexdigest()


def _verify_state(signed_state: str) -> bool:
    """
    Verify that signed_state is '{raw}.{sig}' where sig is the HMAC of raw.
    Uses hmac.compare_digest to prevent timing attacks.
    """
    if not signed_state or "." not in signed_state:
        return False
    raw, _, sig = signed_state.rpartition(".")
    expected_sig = _sign_state(raw)
    return hmac.compare_digest(expected_sig, sig)


router = APIRouter()

# In-memory failed login tracker: {email: [unix_timestamp, ...]}
_failed_attempts: dict[str, list[float]] = {}
_FAIL_WINDOW_SECS = 3600   # 1 hour
_FAIL_THRESHOLD = 3         # alert after N failures in window


def _record_failed_login(email: str, db) -> None:
    """Track failed login attempt; create alert if threshold reached."""
    now = time.time()
    attempts = [t for t in _failed_attempts.get(email, []) if now - t < _FAIL_WINDOW_SECS]
    attempts.append(now)
    _failed_attempts[email] = attempts
    if len(attempts) >= _FAIL_THRESHOLD:
        try:
            from app.utils.alerts import create_alert
            create_alert(
                db,
                "login_failed",
                f"{len(attempts)} ניסיונות כניסה כושלים מהאימייל: {email} (שעה אחרונה)",
                deduplicate_today=True,
            )
            db.commit()
        except Exception:
            pass


class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    therapist_id: int
    full_name: str
    email: str
    must_change_password: bool = False


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    phone: str | None = None
    intended_plan: str | None = None  # marketing attribution from ?plan= URL param
    has_accepted_terms: bool = False   # must be True or registration is rejected


@router.post("/register", response_model=TokenResponse)
async def register(
    request: RegisterRequest,
    db: Session = Depends(get_db)
):
    """Register a new therapist account"""

    therapist_service = TherapistService(db)

    # Guard: terms acceptance is mandatory
    if not request.has_accepted_terms:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="חובה לאשר את תנאי השימוש ומדיניות הפרטיות כדי להמשיך.",
        )

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

        # Persist marketing attribution and consent timestamp
        therapist.accepted_terms_at = datetime.now(timezone.utc)
        if request.intended_plan == 'pro':
            therapist.intended_plan = 'pro'
        db.commit()

        # Create access token
        access_token = create_access_token(
            data={"sub": str(therapist.id)},
            expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        )

        # Admin alert: new signup
        try:
            alert = AdminAlert(
                type="new_signup",
                message=f"מטפל/ת חדש/ה נרשם/ה: {therapist.full_name} ({therapist.email})",
                therapist_id=therapist.id,
            )
            db.add(alert)
            db.commit()
        except Exception:
            pass  # non-blocking

        # Loops.so — fire-and-forget signup notification
        try:
            from app.services.loops_service import notify_loops_signup
            import asyncio
            name_parts = (therapist.full_name or "").split(" ", 1)
            asyncio.create_task(notify_loops_signup(
                email=therapist.email,
                first_name=name_parts[0],
                last_name=name_parts[1] if len(name_parts) > 1 else "",
            ))
        except Exception:
            pass  # non-blocking

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
        _record_failed_login(form_data.username, db)
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

    # Check if blocked by admin
    if therapist.is_blocked:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="החשבון שלך הושהה. פנה לתמיכה.",
        )

    # Update last_login
    try:
        therapist.last_login = datetime.utcnow()
        db.commit()
    except Exception:
        db.rollback()

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
        "must_change_password": bool(therapist.must_change_password),
    }


# ---------------------------------------------------------------------------
# Admin token — issues a short-lived admin JWT for the admin panel
# ---------------------------------------------------------------------------

class AdminTokenRequest(BaseModel):
    email: str
    password: str


class AdminTokenResponse(BaseModel):
    admin_token: str


ADMIN_TOKEN_EXPIRE_MINUTES = 120


@router.post("/admin-token", response_model=AdminTokenResponse)
async def get_admin_token(
    request: AdminTokenRequest,
    db: Session = Depends(get_db),
):
    """
    Issues a 2-hour admin JWT.
    Only works for accounts with is_admin=True.
    Stored in sessionStorage (never localStorage) — not a regular auth token.
    """
    therapist = db.query(Therapist).filter(Therapist.email == request.email).first()
    if not therapist or not verify_password(request.password, therapist.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    if not therapist.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    if therapist.is_blocked or not therapist.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account suspended")

    admin_token = create_access_token(
        data={"sub": str(therapist.id), "is_admin": True},
        expires_delta=timedelta(minutes=ADMIN_TOKEN_EXPIRE_MINUTES),
    )
    return {"admin_token": admin_token}


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
# Change password — required after admin-issued temporary password
# ---------------------------------------------------------------------------

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


@router.post("/change-password", status_code=200)
async def change_password(
    body: ChangePasswordRequest,
    current_therapist: Therapist = Depends(get_current_therapist),
    db: Session = Depends(get_db),
):
    """
    Allow a therapist to change their password.
    Used after an admin sends a temporary password (must_change_password=True).
    Also available as a general self-service password change.
    """
    if len(body.new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="הסיסמה החדשה חייבת להכיל לפחות 8 תווים",
        )

    if not verify_password(body.current_password, current_therapist.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="הסיסמה הזמנית שגויה",
        )

    current_therapist.hashed_password = get_password_hash(body.new_password)
    current_therapist.must_change_password = False
    db.commit()

    return {"success": True}


# ---------------------------------------------------------------------------
# Google OAuth — state generation + callback
# ---------------------------------------------------------------------------

@router.get("/google/state")
async def google_state():
    """
    Generate an HMAC-signed OAuth state token for CSRF protection.

    The frontend calls this before redirecting to Google, stores the signed
    state in sessionStorage, and passes it as the `state` parameter.
    On callback the signed state is sent back here and its HMAC is verified.
    """
    raw = secrets.token_urlsafe(16)
    sig = _sign_state(raw)
    return {"state": f"{raw}.{sig}"}


class GoogleCallbackRequest(BaseModel):
    code: str
    redirect_uri: str
    state: str  # HMAC-signed state — verified server-side for CSRF protection


class GoogleTokenResponse(BaseModel):
    access_token: str
    token_type: str
    therapist_id: int
    full_name: str
    email: str
    is_onboarding_completed: bool


class GoogleCallbackResponse(BaseModel):
    """Discriminated response from /google/callback.
    Existing users: access_token and the usual fields are populated.
    New users (needs consent): needs_consent=True + pending_token + email/full_name.
    """
    # Existing-user fields
    access_token: Optional[str] = None
    token_type: Optional[str] = None
    therapist_id: Optional[int] = None
    full_name: Optional[str] = None
    email: Optional[str] = None
    is_onboarding_completed: Optional[bool] = None
    # New-user consent fields
    needs_consent: bool = False
    pending_token: Optional[str] = None


GOOGLE_PENDING_TOKEN_EXPIRE_MINUTES = 10


@router.post("/google/callback", response_model=GoogleCallbackResponse)
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
    # ── 0. Verify HMAC-signed state (CSRF protection) ────────────────────
    if not _verify_state(request.state):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OAuth state parameter",
        )

    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
        missing = []
        if not settings.GOOGLE_CLIENT_ID:
            missing.append("GOOGLE_CLIENT_ID")
        if not settings.GOOGLE_CLIENT_SECRET:
            missing.append("GOOGLE_CLIENT_SECRET")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Google OAuth is not configured on this server (missing: {', '.join(missing)})",
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
        # Brand-new user — require explicit Terms consent before creating the account.
        # Issue a short-lived signed token containing the Google user info.
        from jose import jwt as jose_jwt
        pending_payload = {
            "sub": google_sub,
            "email": email,
            "name": full_name or email.split("@")[0],
            "is_verified": email_verified,
            "type": "google_pending",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=GOOGLE_PENDING_TOKEN_EXPIRE_MINUTES),
        }
        pending_token = jose_jwt.encode(
            pending_payload,
            settings.SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM,
        )
        return GoogleCallbackResponse(
            needs_consent=True,
            pending_token=pending_token,
            full_name=full_name or email.split("@")[0],
            email=email,
        )

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

    return GoogleCallbackResponse(
        access_token=access_token,
        token_type="bearer",
        therapist_id=therapist.id,
        full_name=therapist.full_name,
        email=therapist.email,
        is_onboarding_completed=onboarding_completed,
        needs_consent=False,
    )


# ---------------------------------------------------------------------------
# Google OAuth — complete signup (new users who have accepted terms)
# ---------------------------------------------------------------------------

class GoogleCompleteSignupRequest(BaseModel):
    pending_token: str       # short-lived JWT issued by /google/callback for new users
    # has_accepted_terms is no longer required here — consent is collected on /register
    # before the Google OAuth flow starts. We still accept it for backwards compat.
    has_accepted_terms: bool = True


@router.post("/google/complete-signup", response_model=GoogleTokenResponse)
async def google_complete_signup(
    request: GoogleCompleteSignupRequest,
    db: Session = Depends(get_db),
):
    """
    Finalize a Google signup for a new user.

    Called only for new users (existing users are handled by /google/callback directly).
    Validates the short-lived pending_token issued by /google/callback, creates the
    therapist account, sets accepted_terms_at, and returns a full JWT.
    Consent is collected on /register before the Google OAuth flow starts.
    """

    # Decode and validate the pending token
    from jose import JWTError, jwt as jose_jwt
    try:
        payload = jose_jwt.decode(
            request.pending_token,
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        if payload.get("type") != "google_pending":
            raise ValueError("Wrong token type")
    except (JWTError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="פג תוקף הבקשה. אנא התחבר עם גוגל מחדש.",
        )

    google_sub: str = payload["sub"]
    email: str = payload["email"]
    full_name: str = payload.get("name", "") or email.split("@")[0]
    is_verified: bool = payload.get("is_verified", False)

    # Guard against double-submit or race: check if account was already created
    therapist = (
        db.query(Therapist).filter(Therapist.google_sub == google_sub).first()
        or db.query(Therapist).filter(Therapist.email == email).first()
    )

    if therapist is None:
        # Create the new account now, with consent timestamp
        therapist = Therapist(
            email=email,
            hashed_password=get_password_hash(secrets.token_urlsafe(32)),
            full_name=full_name,
            auth_provider="google",
            google_sub=google_sub,
            is_active=True,
            is_verified=is_verified,
            accepted_terms_at=datetime.now(timezone.utc),
        )
        db.add(therapist)
        db.commit()
        db.refresh(therapist)

        # Create blank profile (mirrors TherapistService.create_therapist)
        blank_profile = TherapistProfile(
            therapist_id=therapist.id,
            therapeutic_approach=TherapeuticApproach.CBT,
            onboarding_completed=False,
            onboarding_step=0,
        )
        db.add(blank_profile)
        db.commit()
        db.refresh(therapist)

        # Admin alert
        try:
            alert = AdminAlert(
                type="new_signup",
                message=f"מטפל/ת חדש/ה נרשם/ה (גוגל): {therapist.full_name} ({therapist.email})",
                therapist_id=therapist.id,
            )
            db.add(alert)
            db.commit()
        except Exception:
            pass

        # Loops.so — fire-and-forget signup notification
        try:
            from app.services.loops_service import notify_loops_signup
            import asyncio
            name_parts = (therapist.full_name or "").split(" ", 1)
            asyncio.create_task(notify_loops_signup(
                email=therapist.email,
                first_name=name_parts[0],
                last_name=name_parts[1] if len(name_parts) > 1 else "",
            ))
        except Exception:
            pass  # non-blocking
    else:
        # Edge case: account already exists — link Google if not linked yet
        if not therapist.google_sub:
            therapist.google_sub = google_sub
            db.commit()
        # Backfill consent timestamp if missing (existing user completing consent retroactively)
        if therapist.accepted_terms_at is None:
            therapist.accepted_terms_at = datetime.now(timezone.utc)
            db.commit()

    if not therapist.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This account has been deactivated",
        )

    onboarding_completed = bool(therapist.profile and therapist.profile.onboarding_completed)

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
