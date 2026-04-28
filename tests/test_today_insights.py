"""
Tests for GET /therapist/today-insights.

Covers the bug where the query incorrectly referenced SessionSummary.session_id
(which does not exist — the FK lives on Session.summary_id → session_summaries.id).
"""

import pytest
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.models.base import Base
from app.api.deps import get_db, get_current_therapist
from app.models.therapist import Therapist, TherapistProfile, TherapeuticApproach
from app.models.session import Session as TherapySession, SessionSummary, SummaryStatus
from app.models.patient import Patient
from app.models.audit import AuditLog as _AuditLog  # noqa: F401 — ensure table is created
from app.models.message import Message as _Message  # noqa: F401

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

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
def populated_db(db):
    """
    Therapist with one patient who has a today session + one approved summary
    linked via Session.summary_id (the correct FK direction).
    """
    today = date.today()

    therapist = Therapist(
        email="insights@clinic.com",
        hashed_password="x",
        full_name="Dr. Insights",
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

    from app.security.encryption import encrypt_data
    patient = Patient(
        therapist_id=therapist.id,
        full_name_encrypted=encrypt_data("Test Patient"),
    )
    db.add(patient)
    db.flush()

    # Past session with an approved summary
    past_session = TherapySession(
        therapist_id=therapist.id,
        patient_id=patient.id,
        session_date=date(2026, 1, 10),
        session_number=1,
    )
    db.add(past_session)
    db.flush()

    summary = SessionSummary(
        full_summary="The patient discussed anxiety.",
        topics_discussed=["anxiety"],
        interventions_used=["CBT"],
        patient_progress="Good progress.",
        approved_by_therapist=True,
        status=SummaryStatus.APPROVED,
    )
    db.add(summary)
    db.flush()

    # Link via Session.summary_id (the real FK)
    past_session.summary_id = summary.id
    db.flush()

    # Today's session (this is what the endpoint queries)
    today_session = TherapySession(
        therapist_id=therapist.id,
        patient_id=patient.id,
        session_date=today,
        session_number=2,
    )
    db.add(today_session)
    db.commit()

    return {
        "therapist": therapist,
        "patient": patient,
        "today_session": today_session,
        "past_session": past_session,
        "summary": summary,
    }


@pytest.fixture
def client(db, populated_db):
    therapist = populated_db["therapist"]

    def override_get_db():
        try:
            yield db
        finally:
            pass

    def override_get_current_therapist():
        return therapist

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_therapist] = override_get_current_therapist
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestTodayInsightsQuery:
    """The query must use Session.summary_id, never SessionSummary.session_id."""

    def test_does_not_raise_attribute_error(self, client, populated_db):
        """
        Before the fix, this raised:
          AttributeError: type object 'SessionSummary' has no attribute 'session_id'
        The function caught it and returned {"insights": []}.

        After the fix, the query succeeds and proceeds to the AI call.
        We mock the AI agent to avoid real API calls.
        """
        mock_insight = MagicMock()
        mock_insight.patient_id = populated_db["patient"].id
        mock_insight.title = "Session reminder"
        mock_insight.body = "Review anxiety coping strategies."

        mock_result = MagicMock()
        mock_result.insights = [mock_insight]

        mock_agent = AsyncMock()
        mock_agent.generate_today_insights = AsyncMock(return_value=mock_result)
        mock_agent.provider = MagicMock()
        mock_agent.profile = MagicMock()
        mock_agent.profile.language = "he"
        mock_agent.modality_pack = None

        with patch(
            "app.services.therapist_service.TherapistService.get_agent_for_therapist",
            new=AsyncMock(return_value=mock_agent),
        ):
            response = client.get("/api/v1/therapist/today-insights")

        assert response.status_code == 200
        data = response.json()
        assert "insights" in data
        # Must return the mocked insight, not silently fall back to []
        assert len(data["insights"]) == 1
        assert data["insights"][0]["title"] == "Session reminder"

    def test_no_today_sessions_returns_empty(self, db):
        """When there are no sessions today, return empty insights without AI call."""
        therapist = Therapist(
            email="empty@clinic.com",
            hashed_password="x",
            full_name="Dr. Empty",
            is_active=True,
        )
        db.add(therapist)
        db.commit()

        def override_get_db():
            yield db

        def override_get_current_therapist():
            return therapist

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_therapist] = override_get_current_therapist
        try:
            with TestClient(app) as c:
                response = c.get("/api/v1/therapist/today-insights")
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 200
        assert response.json() == {"insights": []}

    def test_session_summary_has_no_session_id_column(self):
        """
        Regression guard: SessionSummary must never gain a session_id column.
        The FK lives on Session.summary_id — reversing it would break the join direction.
        """
        col_names = {c.key for c in SessionSummary.__table__.columns}
        assert "session_id" not in col_names, (
            "SessionSummary must not have session_id — FK lives on Session.summary_id"
        )
        assert "summary_id" in {c.key for c in TherapySession.__table__.columns}, (
            "Session must retain summary_id FK"
        )


class TestAiModelColumnWidth:
    """After migration 043, ai_model is TEXT — no VARCHAR(200) constraint."""

    def test_ai_model_is_text(self):
        from sqlalchemy import Text
        col = SessionSummary.__table__.c["ai_model"]
        assert isinstance(col.type, Text), (
            "ai_model must be Text (not String/VARCHAR) — preventive widening migration 043"
        )
