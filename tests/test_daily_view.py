"""Tests for daily view (sessions by-date) endpoint"""

from datetime import date, datetime, timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.models.base import Base
from app.api.deps import get_db, get_current_therapist
from app.models.therapist import Therapist, TherapistProfile, TherapeuticApproach
from app.models.session import Session as _Session, SessionSummary as _SessionSummary  # noqa: F401
from app.models.patient import Patient as _Patient  # noqa: F401
from app.models.message import Message as _Message  # noqa: F401
from app.models.audit import AuditLog as _AuditLog  # noqa: F401

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_conn, connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db():
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def therapist_with_sessions(db):
    """Create a therapist, patient, and 3 sessions on different dates."""
    from app.models.patient import Patient
    from app.models.session import Session as TherapySession

    today = date.today()
    yesterday = today - timedelta(days=1)
    tomorrow = today + timedelta(days=1)

    therapist = Therapist(
        email="daily@clinic.com",
        hashed_password="fakehash",
        full_name="Dr. Daily",
        is_active=True,
    )
    db.add(therapist)
    db.flush()

    profile = TherapistProfile(
        therapist_id=therapist.id,
        therapeutic_approach=TherapeuticApproach.CBT,
        onboarding_completed=True,
        onboarding_step=5,
    )
    db.add(profile)
    db.flush()

    patient = Patient(
        therapist_id=therapist.id,
        full_name_encrypted="יעל כהן",
    )
    db.add(patient)
    db.flush()

    session_today = TherapySession(
        therapist_id=therapist.id,
        patient_id=patient.id,
        session_date=today,
        start_time=datetime(today.year, today.month, today.day, 10, 0),
        session_number=1,
    )
    session_yesterday = TherapySession(
        therapist_id=therapist.id,
        patient_id=patient.id,
        session_date=yesterday,
        start_time=datetime(yesterday.year, yesterday.month, yesterday.day, 14, 0),
        session_number=2,
    )
    session_tomorrow = TherapySession(
        therapist_id=therapist.id,
        patient_id=patient.id,
        session_date=tomorrow,
        start_time=datetime(tomorrow.year, tomorrow.month, tomorrow.day, 9, 0),
        session_number=3,
    )

    db.add_all([session_today, session_yesterday, session_tomorrow])
    db.commit()
    db.refresh(therapist)

    return {
        "therapist": therapist,
        "patient": patient,
        "today": today,
        "yesterday": yesterday,
        "tomorrow": tomorrow,
        "session_today": session_today,
        "session_yesterday": session_yesterday,
        "session_tomorrow": session_tomorrow,
    }


@pytest.fixture
def client(db, therapist_with_sessions):
    therapist = therapist_with_sessions["therapist"]

    def override_get_db():
        try:
            yield db
        finally:
            pass

    async def override_get_current_therapist():
        return therapist

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_therapist] = override_get_current_therapist

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_sessions_by_date_today(client, therapist_with_sessions):
    """GET /sessions/by-date?date=<today> returns only today's session."""
    today = therapist_with_sessions["today"].isoformat()

    resp = client.get(f"/api/v1/sessions/by-date?date={today}")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["patient_name"] == "יעל כהן"
    assert data[0]["has_summary"] is False
    assert data[0]["session_date"] == today


@pytest.mark.asyncio
async def test_sessions_by_date_yesterday(client, therapist_with_sessions):
    """GET /sessions/by-date?date=<yesterday> returns only yesterday's session."""
    yesterday = therapist_with_sessions["yesterday"].isoformat()

    resp = client.get(f"/api/v1/sessions/by-date?date={yesterday}")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["session_date"] == yesterday


@pytest.mark.asyncio
async def test_sessions_by_date_default_today(client, therapist_with_sessions):
    """GET /sessions/by-date (no param) defaults to today."""
    today = therapist_with_sessions["today"].isoformat()

    resp = client.get("/api/v1/sessions/by-date")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["session_date"] == today


@pytest.mark.asyncio
async def test_sessions_by_date_empty(client, therapist_with_sessions):
    """GET /sessions/by-date for a date with no sessions returns empty list."""
    far_date = "2030-01-01"

    resp = client.get(f"/api/v1/sessions/by-date?date={far_date}")

    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_sessions_by_date_includes_start_time(client, therapist_with_sessions):
    """Response items include start_time."""
    today = therapist_with_sessions["today"].isoformat()

    resp = client.get(f"/api/v1/sessions/by-date?date={today}")

    assert resp.status_code == 200
    data = resp.json()
    assert data[0]["start_time"] is not None
    assert "10:00" in data[0]["start_time"]
