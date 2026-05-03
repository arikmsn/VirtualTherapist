"""
Tests for Green-API quota visibility (HTTP 466 classification and webhook logging).

Covers:
1. HTTP 466 with quota body → rejection_reason set, warning logged with context.
2. Keyword match (no 466) → also classified as quota.
3. Non-quota errors → status FAILED, no rejection_reason set, no crash.
4. Webhook: quotaExceeded → 200 OK, WARNING logged.
5. Webhook: other typeWebhook → 200 OK, INFO logged.
6. Webhook: malformed body → 200 OK, no crash.
"""

import pytest
from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.models.base import Base
from app.api.deps import get_db, get_current_therapist
from app.models.therapist import Therapist, TherapistProfile, TherapeuticApproach
from app.models.message import Message, MessageStatus, MessageDirection
from app.models.patient import Patient
from app.models.audit import AuditLog as _AuditLog  # noqa: F401
from app.services.message_service import _is_greenapi_quota_error, _QUOTA_REJECTION_REASON
from app.services.channels.base import SendResult

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
    therapist = Therapist(
        email="quota@clinic.com",
        hashed_password="x",
        full_name="Dr. Quota",
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

    # A scheduled message ready to deliver
    message = Message(
        therapist_id=therapist.id,
        patient_id=patient.id,
        direction=MessageDirection.TO_PATIENT,
        content="שלום",
        status=MessageStatus.SCHEDULED,
        scheduled_send_at=datetime(2020, 1, 1),  # past → due
        channel="whatsapp",
        recipient_phone="+972501234567",
        message_type="check_in",
        requires_approval=False,
    )
    db.add(message)
    db.commit()
    return {"therapist": therapist, "patient": patient, "message": message}


# ── Unit: _is_greenapi_quota_error ────────────────────────────────────────────

class TestIsGreenapiQuotaError:
    def test_466_is_quota(self):
        assert _is_greenapi_quota_error(466, "") is True

    def test_keyword_CORRESPONDENTS_QUOTA_EXCEEDED(self):
        assert _is_greenapi_quota_error(200, "status: CORRESPONDENTS_QUOTA_EXCEEDED") is True

    def test_keyword_correspondentsStatus(self):
        assert _is_greenapi_quota_error(200, '{"correspondentsStatus": "exceeded"}') is True

    def test_keyword_monthly_quota(self):
        body = "Monthly quota has been exceeded. You can only send from these numbers"
        assert _is_greenapi_quota_error(200, body) is True

    def test_500_generic_error_is_not_quota(self):
        assert _is_greenapi_quota_error(500, "Internal Server Error") is False

    def test_network_error_is_not_quota(self):
        assert _is_greenapi_quota_error(0, "Connection refused") is False

    def test_twilio_63016_is_not_quota(self):
        assert _is_greenapi_quota_error(0, "Error 63016: outside 24h window") is False


# ── Integration: deliver_message classifies quota failures ────────────────────

class TestDeliverMessageQuotaClassification:
    """deliver_message (async path) must set rejection_reason on quota errors."""

    @pytest.mark.asyncio
    async def test_466_sets_rejection_reason(self, db, populated_db, caplog):
        """HTTP 466 → rejection_reason = greenapi_quota_exceeded_correspondents."""
        import logging
        message = populated_db["message"]

        quota_result: SendResult = {
            "status": "failed",
            "provider_id": "",
            "error": "466 Quota",
            "http_status_code": 466,
        }

        from app.services.message_service import MessageService
        svc = MessageService(db)

        with patch(
            "app.services.whatsapp_service.send_whatsapp_message",
            new=AsyncMock(return_value=quota_result),
        ):
            with caplog.at_level(logging.WARNING):
                await svc.deliver_message(message.id)

        db.refresh(message)
        assert message.status == MessageStatus.FAILED
        assert message.rejection_reason == _QUOTA_REJECTION_REASON

        # Log must include message_id, therapist_id, and "quota"
        quota_logs = [r for r in caplog.records if "quota" in r.message.lower()]
        assert quota_logs, "Expected at least one [quota] WARNING log"
        log_text = quota_logs[0].message
        assert str(message.id) in log_text
        assert str(populated_db["therapist"].id) in log_text
        assert "466" in log_text

    @pytest.mark.asyncio
    async def test_non_quota_error_no_rejection_reason(self, db, populated_db):
        """Non-quota failure → FAILED status, rejection_reason stays None."""
        message = populated_db["message"]

        generic_result: SendResult = {
            "status": "failed",
            "provider_id": "",
            "error": "Connection timeout",
            "http_status_code": 0,
        }

        from app.services.message_service import MessageService
        svc = MessageService(db)

        with patch(
            "app.services.whatsapp_service.send_whatsapp_message",
            new=AsyncMock(return_value=generic_result),
        ):
            await svc.deliver_message(message.id)

        db.refresh(message)
        assert message.status == MessageStatus.FAILED
        assert message.rejection_reason is None

    @pytest.mark.asyncio
    async def test_successful_send_not_affected(self, db, populated_db):
        """Successful send → SENT, no rejection_reason."""
        message = populated_db["message"]

        ok_result: SendResult = {
            "status": "sent",
            "provider_id": "msg123",
            "error": "",
            "http_status_code": 200,
        }

        from app.services.message_service import MessageService
        svc = MessageService(db)

        with patch(
            "app.services.whatsapp_service.send_whatsapp_message",
            new=AsyncMock(return_value=ok_result),
        ):
            await svc.deliver_message(message.id)

        db.refresh(message)
        assert message.status == MessageStatus.SENT
        assert message.rejection_reason is None


# ── Integration: _deliver_due_messages_sync classifies quota failures ─────────

class TestSchedulerQuotaClassification:
    """Sync scheduler path must also classify 466 and set rejection_reason."""

    def test_466_from_httpx_sets_rejection_reason(self, populated_db, caplog):
        """Scheduler path: HTTP 466 → rejection_reason set, quota WARNING logged."""
        import logging
        import httpx
        from app.services.message_service import _deliver_due_messages_sync

        message = populated_db["message"]
        message_id = message.id

        mock_response = MagicMock()
        mock_response.status_code = 466
        mock_response.text = '{"status":"CORRESPONDENTS_QUOTA_EXCEEDED"}'
        mock_response.json.return_value = {"status": "CORRESPONDENTS_QUOTA_EXCEEDED"}
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "466 Quota",
            request=MagicMock(),
            response=mock_response,
        )

        # Give the scheduler its own session on the test engine (it will close it itself).
        # Also provide dummy credentials so the guard doesn't short-circuit before httpx.
        with patch("httpx.post", return_value=mock_response), \
             patch("app.core.database.SessionLocal", side_effect=lambda: TestSessionLocal()), \
             patch("app.core.config.settings.GREEN_API_INSTANCE_ID", "test_instance"), \
             patch("app.core.config.settings.GREEN_API_TOKEN", "test_token"):
            with caplog.at_level(logging.WARNING):
                _deliver_due_messages_sync()

        # Verify state via a fresh read session
        check_session = TestSessionLocal()
        try:
            updated = check_session.query(Message).filter(Message.id == message_id).first()
            assert updated.status == MessageStatus.FAILED
            assert updated.rejection_reason == _QUOTA_REJECTION_REASON
        finally:
            check_session.close()

        quota_logs = [r for r in caplog.records if "quota" in r.message.lower()]
        assert quota_logs, "Expected at least one [quota] WARNING from scheduler"
        log_text = quota_logs[0].message
        assert str(message_id) in log_text
        assert "466" in log_text


# ── Webhook endpoint tests ────────────────────────────────────────────────────

@pytest.fixture
def webhook_client():
    with TestClient(app) as c:
        yield c


class TestWhatsappWebhook:
    def test_quota_exceeded_returns_200(self, webhook_client, caplog):
        import logging
        payload = {
            "typeWebhook": "quotaExceeded",
            "quotaData": {
                "method": "correspondents",
                "status": "CORRESPONDENTS_QUOTA_EXCEEDED",
                "used": 3,
                "total": 3,
                "description": "Allowed: [972501234567, 972509999999, 972507777777]",
            },
        }
        with caplog.at_level(logging.WARNING):
            resp = webhook_client.post("/api/v1/whatsapp/webhook", json=payload)

        assert resp.status_code == 200
        assert resp.json() == {"ok": True}

        quota_logs = [r for r in caplog.records if "quotaExceeded" in r.message]
        assert quota_logs, "Expected WARNING log for quotaExceeded webhook"
        log_text = quota_logs[0].message
        assert "CORRESPONDENTS_QUOTA_EXCEEDED" in log_text
        assert "used=3" in log_text
        assert "total=3" in log_text

    def test_other_webhook_type_returns_200(self, webhook_client, caplog):
        import logging
        payload = {"typeWebhook": "incomingMessageReceived", "data": {}}
        with caplog.at_level(logging.INFO):
            resp = webhook_client.post("/api/v1/whatsapp/webhook", json=payload)

        assert resp.status_code == 200
        assert resp.json() == {"ok": True}

        info_logs = [r for r in caplog.records if "incomingMessageReceived" in r.message]
        assert info_logs

    def test_malformed_body_returns_200(self, webhook_client):
        resp = webhook_client.post(
            "/api/v1/whatsapp/webhook",
            data="not json",
            headers={"Content-Type": "text/plain"},
        )
        assert resp.status_code == 200
        assert resp.json() == {"ok": True}

    def test_empty_json_returns_200(self, webhook_client):
        resp = webhook_client.post("/api/v1/whatsapp/webhook", json={})
        assert resp.status_code == 200
