"""
Tests for send_or_schedule_message timezone handling.

Regression test for: TypeError: can't compare offset-naive and
offset-aware datetimes (send_at from Pydantic is tz-aware; was comparing
against naive datetime.utcnow()).
"""

from datetime import datetime, timezone, timedelta, date
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.base import Base
from app.models.therapist import Therapist, TherapistProfile, TherapeuticApproach
from app.models.patient import Patient as _Patient  # noqa: F401 — needed for FK
from app.models.session import Session as _Session  # noqa: F401 — needed for FK
from app.models.message import Message, MessageStatus, MessageDirection
from app.models.audit import AuditLog as _AuditLog  # noqa: F401
from app.services.message_service import MessageService

# --------------------------------------------------------------------------- #
# In-memory SQLite setup
# --------------------------------------------------------------------------- #

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
def draft_message(db):
    """Minimal therapist + patient + draft message in the test DB."""
    from app.models.patient import Patient

    therapist = Therapist(
        email="tz_test@clinic.com",
        hashed_password="fakehash",
        full_name="Dr. Timezone",
        is_active=True,
    )
    db.add(therapist)
    db.flush()

    db.add(TherapistProfile(
        therapist_id=therapist.id,
        therapeutic_approach=TherapeuticApproach.CBT,
        onboarding_completed=True,
        onboarding_step=5,
    ))
    db.flush()

    patient = Patient(
        therapist_id=therapist.id,
        full_name_encrypted="Test Patient",
    )
    db.add(patient)
    db.flush()

    message = Message(
        therapist_id=therapist.id,
        patient_id=patient.id,
        direction=MessageDirection.TO_PATIENT,
        content="Hello, this is a test reminder.",
        message_type="task_reminder",
        status=MessageStatus.DRAFT,   # service expects DRAFT before confirm
        recipient_phone="+972501234567",
        requires_approval=False,
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    db.refresh(therapist)

    return {"therapist": therapist, "message": message}


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _make_service(db):
    svc = MessageService(db)
    svc.audit_service = MagicMock()
    svc.audit_service.log_action = AsyncMock()
    return svc


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_send_at_past_tz_aware_triggers_immediate_delivery(db, draft_message):
    """
    When send_at is tz-aware and in the past, deliver_message should be called
    immediately — no TypeError from naive/aware comparison.
    """
    msg = draft_message["message"]
    therapist = draft_message["therapist"]

    # send_at 10 minutes ago — tz-aware UTC (as Pydantic sends it)
    send_at = datetime.now(timezone.utc) - timedelta(minutes=10)

    svc = _make_service(db)

    with patch.object(svc, "deliver_message", new_callable=AsyncMock) as mock_deliver:
        mock_deliver.return_value = {"id": msg.id, "status": "sent"}

        # Must NOT raise TypeError
        result = await svc.send_or_schedule_message(
            message_id=msg.id,
            therapist_id=therapist.id,
            final_content=msg.content,
            recipient_phone=msg.recipient_phone,
            send_at=send_at,
        )

    mock_deliver.assert_awaited_once_with(msg.id)


@pytest.mark.asyncio
async def test_send_at_future_tz_aware_schedules(db, draft_message):
    """
    When send_at is tz-aware and in the future, the message should be
    marked SCHEDULED and APScheduler.add_job called — not deliver_message.
    """
    msg = draft_message["message"]
    therapist = draft_message["therapist"]

    # send_at 5 minutes in the future — tz-aware UTC
    send_at = datetime.now(timezone.utc) + timedelta(minutes=5)

    svc = _make_service(db)

    with patch.object(svc, "deliver_message", new_callable=AsyncMock) as mock_deliver, \
         patch("app.core.scheduler.scheduler") as mock_scheduler:

        mock_scheduler.add_job = MagicMock()

        await svc.send_or_schedule_message(
            message_id=msg.id,
            therapist_id=therapist.id,
            final_content=msg.content,
            recipient_phone=msg.recipient_phone,
            send_at=send_at,
        )

    # deliver_message should NOT have been called
    mock_deliver.assert_not_awaited()

    # APScheduler job should have been registered
    mock_scheduler.add_job.assert_called_once()
    call_kwargs = mock_scheduler.add_job.call_args
    assert call_kwargs.kwargs.get("run_date") == send_at or \
           call_kwargs.args[2] == send_at or \
           call_kwargs.kwargs.get("run_date") is not None

    # Message status in DB should be SCHEDULED
    db.refresh(msg)
    assert msg.status == MessageStatus.SCHEDULED
    # SQLite DateTime columns strip tzinfo on retrieval (returns naive UTC).
    # Compare against the naive equivalent of the tz-aware send_at.
    assert msg.scheduled_send_at == send_at.replace(tzinfo=None)


@pytest.mark.asyncio
async def test_send_at_none_triggers_immediate_delivery(db, draft_message):
    """send_at=None should always deliver immediately."""
    msg = draft_message["message"]
    therapist = draft_message["therapist"]

    svc = _make_service(db)

    with patch.object(svc, "deliver_message", new_callable=AsyncMock) as mock_deliver:
        mock_deliver.return_value = {"id": msg.id, "status": "sent"}

        await svc.send_or_schedule_message(
            message_id=msg.id,
            therapist_id=therapist.id,
            final_content=msg.content,
            recipient_phone=msg.recipient_phone,
            send_at=None,
        )

    mock_deliver.assert_awaited_once_with(msg.id)


@pytest.mark.asyncio
async def test_send_at_naive_is_normalized_to_utc(db, draft_message):
    """
    If send_at arrives as naive (no tzinfo) it should be treated as UTC
    and the comparison must not raise TypeError.
    """
    msg = draft_message["message"]
    therapist = draft_message["therapist"]

    # Naive datetime in the future (no tzinfo)
    send_at_naive = datetime.utcnow() + timedelta(minutes=5)
    assert send_at_naive.tzinfo is None  # confirm it's naive

    svc = _make_service(db)

    with patch.object(svc, "deliver_message", new_callable=AsyncMock), \
         patch("app.core.scheduler.scheduler") as mock_scheduler:

        mock_scheduler.add_job = MagicMock()

        # Must NOT raise TypeError
        await svc.send_or_schedule_message(
            message_id=msg.id,
            therapist_id=therapist.id,
            final_content=msg.content,
            recipient_phone=msg.recipient_phone,
            send_at=send_at_naive,
        )

    mock_scheduler.add_job.assert_called_once()


@pytest.mark.asyncio
async def test_future_send_at_never_delivers_immediately(db, draft_message):
    """
    Regression: send_at 5 minutes in the future must NOT trigger
    deliver_message immediately.  The bug was that datetime.utcnow() (naive)
    was compared against a tz-aware send_at -> TypeError, which masked the
    scheduling path entirely.  After the fix both sides are tz-aware UTC and
    the comparison must correctly route to the scheduler, not to delivery.
    """
    msg = draft_message["message"]
    therapist = draft_message["therapist"]

    # Simulate what Pydantic produces when the frontend sends
    # e.g. "2026-02-23T18:05:00.000Z" (UTC ISO string from buildSendAt())
    send_at = datetime.now(timezone.utc) + timedelta(minutes=5)
    assert send_at.tzinfo is not None  # must be tz-aware

    svc = _make_service(db)

    with patch.object(svc, "deliver_message", new_callable=AsyncMock) as mock_deliver, \
         patch("app.core.scheduler.scheduler") as mock_scheduler:

        mock_scheduler.add_job = MagicMock()

        await svc.send_or_schedule_message(
            message_id=msg.id,
            therapist_id=therapist.id,
            final_content=msg.content,
            recipient_phone=msg.recipient_phone,
            send_at=send_at,
        )

    # CRITICAL: must NOT deliver immediately
    mock_deliver.assert_not_awaited()

    # Must register an APScheduler job
    mock_scheduler.add_job.assert_called_once()

    # Message must be SCHEDULED, not SENT
    db.refresh(msg)
    assert msg.status == MessageStatus.SCHEDULED
    # scheduled_send_at stored as naive UTC (SQLite strips tzinfo)
    assert msg.scheduled_send_at == send_at.replace(tzinfo=None)
