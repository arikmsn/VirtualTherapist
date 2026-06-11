"""
Endpoint tests for the Phase 10 task-based summary flows.

These mock the CORRECT seam: TherapistService.get_agent_for_therapist returns a
fake agent whose provider.generate is an AsyncMock, so the real service code
(_run_ai_task → parse_strict → fallback → persistence) is exercised end-to-end.
"""

import json
import types
from datetime import date

import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.models.base import Base
from app.api.deps import get_db, get_current_therapist
from app.models.therapist import Therapist, TherapistProfile, TherapeuticApproach
from app.models.session import (
    Session as TherapySession,
    SessionSummary,
    SummaryStatus,
)
from app.models.patient import Patient
from app.models.ai_log import AIGenerationLog
from app.ai.models import FlowType, GenerationResult


engine = create_engine(
    "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
)


@event.listens_for(engine, "connect")
def _pragma(dbapi_conn, rec):
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA foreign_keys=ON")
    cur.close()


TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db():
    s = TestSessionLocal()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture
def world(db):
    therapist = Therapist(email="t@clinic.com", hashed_password="x", full_name="Dr T", is_active=True)
    db.add(therapist)
    db.flush()
    db.add(TherapistProfile(
        therapist_id=therapist.id, therapeutic_approach=TherapeuticApproach.CBT,
        onboarding_completed=True, onboarding_step=5,
    ))
    db.flush()
    patient = Patient(therapist_id=therapist.id, full_name_encrypted="Enc")
    db.add(patient)
    db.flush()
    session = TherapySession(
        therapist_id=therapist.id, patient_id=patient.id,
        session_date=date(2026, 2, 17), session_number=1,
    )
    db.add(session)
    db.commit()
    db.refresh(therapist)
    db.refresh(session)
    return {"therapist": therapist, "patient": patient, "session": session}


@pytest.fixture
def client(db, world):
    therapist = world["therapist"]

    def override_get_db():
        yield db

    async def override_current():
        return therapist

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_therapist] = override_current
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _fake_agent(generate_content: str, flow_type=FlowType.SUMMARY_SUGGEST):
    """Build a fake agent whose provider.generate returns canned content."""
    provider = types.SimpleNamespace()
    provider.generate = AsyncMock(return_value=GenerationResult(
        content=generate_content,
        model_used="test-model",
        provider="anthropic",
        flow_type=flow_type,
        prompt_tokens=10,
        completion_tokens=20,
        generation_ms=50,
        route_reason=f"flow:{flow_type.value},tier:standard",
    ))
    return types.SimpleNamespace(provider=provider, modality_pack=None, system_prompt="sys", _last_result=None)


def _make_summary(db, world, *, full_summary="original draft", approved=False):
    summary = SessionSummary(
        full_summary=full_summary,
        ai_draft_text="THE ORIGINAL AI DRAFT",
        generated_from="text",
        status=SummaryStatus.APPROVED if approved else SummaryStatus.DRAFT,
        approved_by_therapist=approved,
        therapist_edited=False,
    )
    db.add(summary)
    db.flush()
    world["session"].summary_id = summary.id
    db.commit()
    db.refresh(summary)
    return summary


# ── source_save: NO AI ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_source_save_makes_no_ai_call(client, world, db):
    sid = world["session"].id
    with patch(
        "app.services.therapist_service.TherapistService.get_agent_for_therapist",
        new_callable=AsyncMock,
    ) as mock_agent:
        resp = client.post(
            f"/api/v1/sessions/{sid}/summary/source-save",
            json={"source_text": "my own clinical notes", "source_origin": "manual"},
        )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["generated_from"] == "manual"
    assert data["full_summary"] == "my own clinical notes"
    assert data["notes_input"] == "my own clinical notes"
    assert data["approved_by_therapist"] is False
    # No agent was ever built → no AI path
    mock_agent.assert_not_called()
    # No AIGenerationLog row written
    assert db.query(AIGenerationLog).count() == 0


@pytest.mark.asyncio
async def test_source_save_transcription_provenance(client, world, db):
    sid = world["session"].id
    resp = client.post(
        f"/api/v1/sessions/{sid}/summary/source-save",
        json={"source_text": "[קטע 1] hello", "source_origin": "transcription"},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["generated_from"] == "manual_transcript"
    assert data["transcript"] == "[קטע 1] hello"
    assert data["notes_input"] is None


@pytest.mark.asyncio
async def test_source_save_empty_text_400(client, world):
    sid = world["session"].id
    resp = client.post(
        f"/api/v1/sessions/{sid}/summary/source-save",
        json={"source_text": "   ", "source_origin": "manual"},
    )
    assert resp.status_code == 400


# ── source_summary_suggest: advisory only ─────────────────────────────────────

@pytest.mark.asyncio
async def test_suggest_returns_suggestions_not_summary(client, world, db):
    sid = world["session"].id
    content = json.dumps({
        "suggestions": [{"category": "missing", "text": "Add mood observation", "severity": "info"}],
        "overall_note": "Looks solid overall.",
    })
    with patch(
        "app.services.therapist_service.TherapistService.get_agent_for_therapist",
        new_callable=AsyncMock, return_value=_fake_agent(content, FlowType.SUMMARY_SUGGEST),
    ):
        resp = client.post(f"/api/v1/sessions/{sid}/summary/suggest", json={"source_text": "notes"})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "suggestions" in data
    assert "full_summary" not in data and "revised_summary" not in data
    assert data["suggestions"][0]["category"] == "missing"
    # No summary persisted by suggest
    assert db.query(SessionSummary).count() == 0
    # One AIGenerationLog row tagged with the task
    rows = db.query(AIGenerationLog).all()
    assert len(rows) == 1
    assert "task:source_summary_suggest" in rows[0].route_reason


@pytest.mark.asyncio
async def test_suggest_rejects_rewrite_field(client, world):
    sid = world["session"].id
    # Model tries to smuggle a rewrite → strict validation rejects → empty scaffold
    content = json.dumps({"suggestions": [], "overall_note": None, "rewritten_summary": "SNEAKY"})
    with patch(
        "app.services.therapist_service.TherapistService.get_agent_for_therapist",
        new_callable=AsyncMock, return_value=_fake_agent(content, FlowType.SUMMARY_SUGGEST),
    ):
        resp = client.post(f"/api/v1/sessions/{sid}/summary/suggest", json={"source_text": "notes"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["suggestions"] == []
    assert "rewritten_summary" not in data


@pytest.mark.asyncio
async def test_suggest_provider_unavailable_503(client, world):
    sid = world["session"].id
    agent = types.SimpleNamespace(provider=None, modality_pack=None, system_prompt="s", _last_result=None)
    with patch(
        "app.services.therapist_service.TherapistService.get_agent_for_therapist",
        new_callable=AsyncMock, return_value=agent,
    ):
        resp = client.post(f"/api/v1/sessions/{sid}/summary/suggest", json={"source_text": "notes"})
    assert resp.status_code == 503


# ── ai_summary_revise: single-shot ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_revise_single_shot(client, world, db):
    sid = world["session"].id
    _make_summary(db, world, full_summary="original draft")
    content = json.dumps({"revised_summary": "revised draft text", "change_note": "shortened", "confidence": 0.9})
    agent = _fake_agent(content, FlowType.SUMMARY_REVISE)
    with patch(
        "app.services.therapist_service.TherapistService.get_agent_for_therapist",
        new_callable=AsyncMock, return_value=agent,
    ):
        resp = client.post(f"/api/v1/sessions/{sid}/summary/revise", json={"instruction": "make it shorter"})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["full_summary"] == "revised draft text"
    assert data["status"] == "draft"
    assert data["approved_by_therapist"] is False
    # Single provider call
    agent.provider.generate.assert_awaited_once()
    # ai_draft_text (immutable original) untouched
    refreshed = db.query(SessionSummary).first()
    assert refreshed.ai_draft_text == "THE ORIGINAL AI DRAFT"


@pytest.mark.asyncio
async def test_revise_resets_approved_to_draft(client, world, db):
    sid = world["session"].id
    _make_summary(db, world, full_summary="approved text", approved=True)
    content = json.dumps({"revised_summary": "now revised", "change_note": None, "confidence": 0.8})
    with patch(
        "app.services.therapist_service.TherapistService.get_agent_for_therapist",
        new_callable=AsyncMock, return_value=_fake_agent(content, FlowType.SUMMARY_REVISE),
    ):
        resp = client.post(f"/api/v1/sessions/{sid}/summary/revise", json={"instruction": "tweak"})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "draft"
    assert data["approved_by_therapist"] is False
    assert data["full_summary"] == "now revised"


@pytest.mark.asyncio
async def test_revise_no_existing_summary_400(client, world):
    sid = world["session"].id
    with patch(
        "app.services.therapist_service.TherapistService.get_agent_for_therapist",
        new_callable=AsyncMock, return_value=_fake_agent("{}", FlowType.SUMMARY_REVISE),
    ):
        resp = client.post(f"/api/v1/sessions/{sid}/summary/revise", json={"instruction": "x"})
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_revise_malformed_json_keeps_original(client, world, db):
    sid = world["session"].id
    _make_summary(db, world, full_summary="keep me intact")
    with patch(
        "app.services.therapist_service.TherapistService.get_agent_for_therapist",
        new_callable=AsyncMock, return_value=_fake_agent("not json at all", FlowType.SUMMARY_REVISE),
    ):
        resp = client.post(f"/api/v1/sessions/{sid}/summary/revise", json={"instruction": "x"})
    assert resp.status_code == 200
    data = resp.json()
    # passthrough_original — draft unchanged, never corrupted, never 500
    assert data["full_summary"] == "keep me intact"
