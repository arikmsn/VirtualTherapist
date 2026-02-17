"""Tests for AI session summary generation endpoint"""

import json
from datetime import date
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.models.base import Base
from app.api.deps import get_db, get_current_therapist
from app.models.therapist import Therapist, TherapistProfile, TherapeuticApproach
from app.models.session import Session as _Session, SessionSummary as _SessionSummary  # noqa: F401
from app.models.patient import Patient as _Patient  # noqa: F401
from app.models.message import Message as _Message  # noqa: F401
from app.models.audit import AuditLog as _AuditLog  # noqa: F401
from app.core.agent import SessionSummaryResult, PatientInsightResult, SessionPrepBriefResult

# In-memory SQLite for tests — use StaticPool so all connections share one DB
from sqlalchemy.pool import StaticPool

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
    """Create all tables before each test, drop after."""
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
def therapist_with_patient(db):
    """Create a therapist, profile, patient, and session in the test DB."""
    from app.models.patient import Patient
    from app.models.session import Session as TherapySession

    therapist = Therapist(
        email="test@clinic.com",
        hashed_password="fakehash",
        full_name="Dr. Test",
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
        full_name_encrypted="Test Patient",
    )
    db.add(patient)
    db.flush()

    session = TherapySession(
        therapist_id=therapist.id,
        patient_id=patient.id,
        session_date=date(2026, 2, 17),
        session_number=1,
    )
    db.add(session)
    db.commit()
    db.refresh(therapist)
    db.refresh(session)

    return {"therapist": therapist, "patient": patient, "session": session}


@pytest.fixture
def client(db, therapist_with_patient):
    """FastAPI test client with overridden deps."""
    therapist = therapist_with_patient["therapist"]

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


MOCK_SUMMARY_JSON = json.dumps({
    "topics_discussed": ["חרדה חברתית", "הימנעות ממצבים חברתיים"],
    "interventions_used": ["חשיפה הדרגתית", "רה-סטרוקטוריזציה קוגניטיבית"],
    "patient_progress": "שיפור קל ביכולת להיות במצבים חברתיים קטנים",
    "homework_assigned": ["תרגול נשימה יומי", "יומן מחשבות אוטומטיות"],
    "next_session_plan": "המשך עבודה על חשיפה הדרגתית למצבים חברתיים",
    "mood_observed": "חרדתי אך משתף פעולה",
    "risk_assessment": "ללא סיכון מיוחד",
    "full_summary": "המטופל הגיע לפגישה השבועית. דיווח על שיפור קל בחרדה החברתית."
})


@pytest.mark.asyncio
async def test_generate_summary_happy_path(client, therapist_with_patient):
    """POST /{session_id}/summary/from-text returns structured summary."""
    session_id = therapist_with_patient["session"].id

    with patch(
        "app.core.agent.TherapyAgent.generate_session_summary",
        new_callable=AsyncMock,
    ) as mock_gen:
        mock_gen.return_value = SessionSummaryResult(
            topics_discussed=["חרדה חברתית", "הימנעות ממצבים חברתיים"],
            interventions_used=["חשיפה הדרגתית", "רה-סטרוקטוריזציה קוגניטיבית"],
            patient_progress="שיפור קל ביכולת להיות במצבים חברתיים קטנים",
            homework_assigned=["תרגול נשימה יומי", "יומן מחשבות אוטומטיות"],
            next_session_plan="המשך עבודה על חשיפה הדרגתית למצבים חברתיים",
            mood_observed="חרדתי אך משתף פעולה",
            risk_assessment="ללא סיכון מיוחד",
            full_summary="המטופל הגיע לפגישה השבועית. דיווח על שיפור קל בחרדה החברתית.",
        )

        resp = client.post(
            f"/api/v1/sessions/{session_id}/summary/from-text",
            json={"notes": "המטופל דיווח על שיפור קל בחרדה. עבדנו על חשיפה הדרגתית."},
        )

    assert resp.status_code == 200, resp.text
    data = resp.json()

    # Verify structured fields
    assert data["topics_discussed"] == ["חרדה חברתית", "הימנעות ממצבים חברתיים"]
    assert data["interventions_used"] == ["חשיפה הדרגתית", "רה-סטרוקטוריזציה קוגניטיבית"]
    assert data["patient_progress"] == "שיפור קל ביכולת להיות במצבים חברתיים קטנים"
    assert len(data["homework_assigned"]) == 2
    assert data["risk_assessment"] == "ללא סיכון מיוחד"
    assert data["generated_from"] == "text"
    assert data["approved_by_therapist"] is False
    assert data["id"] is not None
    assert data["created_at"] is not None


@pytest.mark.asyncio
async def test_get_summary_after_generation(client, therapist_with_patient):
    """GET /{session_id}/summary returns the previously generated summary."""
    session_id = therapist_with_patient["session"].id

    # First generate
    with patch(
        "app.core.agent.TherapyAgent.generate_session_summary",
        new_callable=AsyncMock,
    ) as mock_gen:
        mock_gen.return_value = SessionSummaryResult(
            topics_discussed=["נושא 1"],
            interventions_used=["התערבות 1"],
            patient_progress="התקדמות",
            homework_assigned=["משימה 1"],
            next_session_plan="תוכנית",
            mood_observed="טוב",
            risk_assessment="ללא",
            full_summary="סיכום מלא",
        )

        client.post(
            f"/api/v1/sessions/{session_id}/summary/from-text",
            json={"notes": "רשימות"},
        )

    # Then GET
    resp = client.get(f"/api/v1/sessions/{session_id}/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert data["full_summary"] == "סיכום מלא"
    assert data["topics_discussed"] == ["נושא 1"]


@pytest.mark.asyncio
async def test_get_summary_404_when_none(client, therapist_with_patient):
    """GET /{session_id}/summary returns 404 when no summary exists."""
    session_id = therapist_with_patient["session"].id
    resp = client.get(f"/api/v1/sessions/{session_id}/summary")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_generate_summary_missing_ai_key(client, therapist_with_patient):
    """POST returns 503 when AI client is not initialized."""
    session_id = therapist_with_patient["session"].id

    with patch(
        "app.core.agent.TherapyAgent.generate_session_summary",
        new_callable=AsyncMock,
        side_effect=RuntimeError("AI client not initialized."),
    ):
        resp = client.post(
            f"/api/v1/sessions/{session_id}/summary/from-text",
            json={"notes": "רשימות"},
        )

    assert resp.status_code == 503
    assert "AI client not initialized" in resp.json()["detail"]


def _create_summary_via_api(client, session_id):
    """Helper: generate a summary so we can test PATCH."""
    with patch(
        "app.core.agent.TherapyAgent.generate_session_summary",
        new_callable=AsyncMock,
    ) as mock_gen:
        mock_gen.return_value = SessionSummaryResult(
            topics_discussed=["נושא 1"],
            interventions_used=["התערבות 1"],
            patient_progress="התקדמות",
            homework_assigned=["משימה 1"],
            next_session_plan="תוכנית",
            mood_observed="טוב",
            risk_assessment="ללא",
            full_summary="סיכום מלא",
        )
        resp = client.post(
            f"/api/v1/sessions/{session_id}/summary/from-text",
            json={"notes": "רשימות"},
        )
    assert resp.status_code == 200
    return resp.json()


@pytest.mark.asyncio
async def test_patch_summary_edit_content(client, therapist_with_patient):
    """PATCH /{session_id}/summary updates content and marks as edited."""
    session_id = therapist_with_patient["session"].id
    _create_summary_via_api(client, session_id)

    resp = client.patch(
        f"/api/v1/sessions/{session_id}/summary",
        json={
            "full_summary": "סיכום מעודכן",
            "patient_progress": "התקדמות חדשה",
        },
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["full_summary"] == "סיכום מעודכן"
    assert data["patient_progress"] == "התקדמות חדשה"
    assert data["therapist_edited"] is True
    assert data["status"] == "draft"


@pytest.mark.asyncio
async def test_patch_summary_approve(client, therapist_with_patient):
    """PATCH /{session_id}/summary with status=approved approves the summary."""
    session_id = therapist_with_patient["session"].id
    _create_summary_via_api(client, session_id)

    resp = client.patch(
        f"/api/v1/sessions/{session_id}/summary",
        json={"status": "approved"},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "approved"
    assert data["approved_by_therapist"] is True


@pytest.mark.asyncio
async def test_patient_summaries_list(client, therapist_with_patient):
    """GET /patients/{patient_id}/summaries returns per-patient summary list."""
    session_id = therapist_with_patient["session"].id
    patient_id = therapist_with_patient["patient"].id
    _create_summary_via_api(client, session_id)

    resp = client.get(f"/api/v1/patients/{patient_id}/summaries")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["session_id"] == session_id
    assert data[0]["summary"]["full_summary"] == "סיכום מלא"


@pytest.mark.asyncio
async def test_patient_summaries_empty(client, therapist_with_patient):
    """GET /patients/{patient_id}/summaries returns empty list when no summaries."""
    patient_id = therapist_with_patient["patient"].id

    resp = client.get(f"/api/v1/patients/{patient_id}/summaries")

    assert resp.status_code == 200
    assert resp.json() == []


def _create_approved_summary(client, session_id):
    """Helper: generate + approve a summary."""
    _create_summary_via_api(client, session_id)
    client.patch(
        f"/api/v1/sessions/{session_id}/summary",
        json={"status": "approved"},
    )


@pytest.mark.asyncio
async def test_patient_insight_happy_path(client, therapist_with_patient):
    """POST /patients/{id}/insight-summary returns structured insight."""
    session_id = therapist_with_patient["session"].id
    patient_id = therapist_with_patient["patient"].id
    _create_approved_summary(client, session_id)

    with patch(
        "app.core.agent.TherapyAgent.generate_patient_insight_summary",
        new_callable=AsyncMock,
    ) as mock_insight:
        mock_insight.return_value = PatientInsightResult(
            overview="סקירה כללית של מהלך הטיפול",
            progress="שיפור הדרגתי בתפקוד",
            patterns=["דפוס הימנעות חוזר", "שיפור בביטוי רגשי"],
            risks=["סיכון נמוך, יש לעקוב אחרי דפוסי שינה"],
            suggestions_for_next_sessions=["להמשיך חשיפה הדרגתית", "לעבוד על ויסות רגשי"],
        )

        resp = client.post(f"/api/v1/patients/{patient_id}/insight-summary")

    assert resp.status_code == 200
    data = resp.json()
    assert data["overview"] == "סקירה כללית של מהלך הטיפול"
    assert data["progress"] == "שיפור הדרגתי בתפקוד"
    assert len(data["patterns"]) == 2
    assert len(data["risks"]) == 1
    assert len(data["suggestions_for_next_sessions"]) == 2


@pytest.mark.asyncio
async def test_patient_insight_no_approved_summaries(client, therapist_with_patient):
    """POST /patients/{id}/insight-summary returns 400 when no approved summaries."""
    patient_id = therapist_with_patient["patient"].id

    resp = client.post(f"/api/v1/patients/{patient_id}/insight-summary")

    assert resp.status_code == 400
    assert "סיכומים מאושרים" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_patient_insight_with_draft_only(client, therapist_with_patient):
    """POST returns 400 when summaries exist but none are approved."""
    session_id = therapist_with_patient["session"].id
    patient_id = therapist_with_patient["patient"].id
    # Create but do NOT approve
    _create_summary_via_api(client, session_id)

    resp = client.post(f"/api/v1/patients/{patient_id}/insight-summary")

    assert resp.status_code == 400
    assert "סיכומים מאושרים" in resp.json()["detail"]


# --- Prep Brief Tests ---


@pytest.mark.asyncio
async def test_prep_brief_happy_path(client, therapist_with_patient):
    """POST /sessions/{id}/prep-brief returns structured prep brief."""
    session_id = therapist_with_patient["session"].id
    _create_approved_summary(client, session_id)

    with patch(
        "app.core.agent.TherapyAgent.generate_session_prep_brief",
        new_callable=AsyncMock,
    ) as mock_prep:
        mock_prep.return_value = SessionPrepBriefResult(
            quick_overview="המטופל מראה שיפור הדרגתי",
            recent_progress="שיפור בחרדה חברתית",
            key_points_to_revisit=["יומן מחשבות", "חשיפה הדרגתית"],
            watch_out_for=["דפוסי הימנעות"],
            ideas_for_this_session=["תרגול ויסות רגשי", "סקירת משימות בית"],
        )

        resp = client.post(f"/api/v1/sessions/{session_id}/prep-brief")

    assert resp.status_code == 200
    data = resp.json()
    assert data["quick_overview"] == "המטופל מראה שיפור הדרגתי"
    assert len(data["key_points_to_revisit"]) == 2
    assert len(data["watch_out_for"]) == 1
    assert len(data["ideas_for_this_session"]) == 2


@pytest.mark.asyncio
async def test_prep_brief_no_approved_summaries(client, therapist_with_patient):
    """POST /sessions/{id}/prep-brief returns 400 when no approved summaries."""
    session_id = therapist_with_patient["session"].id

    resp = client.post(f"/api/v1/sessions/{session_id}/prep-brief")

    assert resp.status_code == 400
    assert "סיכומים מאושרים" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_prep_brief_session_not_found(client, therapist_with_patient):
    """POST /sessions/9999/prep-brief returns 400 for non-existent session."""
    resp = client.post("/api/v1/sessions/9999/prep-brief")

    assert resp.status_code == 400
