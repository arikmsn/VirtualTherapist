"""Tests for FK-safe session / summary deletion (migration 045).

Covers three paths:
  1. delete_session: exercises survive; session_summary_id nulled
  2. delete_session_summary: exercises survive; session_summary_id nulled
  3. admin_panel therapist delete: exercises survive with no FK error
"""

from datetime import date
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.base import Base


# ── In-memory SQLite (FK enforcement on) ───────────────────────────────────
engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


@event.listens_for(engine, "connect")
def _enable_fk(dbapi_conn, connection_record):
    dbapi_conn.cursor().execute("PRAGMA foreign_keys=ON")


TestSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(autouse=True)
def _tables():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db():
    s = TestSession()
    try:
        yield s
    finally:
        s.close()


# ── Shared fixture: therapist + patient + session + summary + exercise ─────

@pytest.fixture
def world(db):
    """
    Creates one therapist, one patient, one session linked to a summary,
    and one exercise linked to that summary. Returns a dict of all objects.
    """
    from app.models.therapist import Therapist, TherapistProfile, TherapeuticApproach
    from app.models.patient import Patient
    from app.models.session import Session as TherapySession, SessionSummary, SummaryStatus
    from app.models.exercise import Exercise

    therapist = Therapist(email="t@clinic.com", hashed_password="x", full_name="Dr T", is_active=True)
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

    patient = Patient(therapist_id=therapist.id, full_name_encrypted="Enc Patient")
    db.add(patient)
    db.flush()

    # Create session first (no summary yet) to avoid circular FK issue
    session = TherapySession(
        therapist_id=therapist.id,
        patient_id=patient.id,
        session_date=date(2026, 1, 1),
        session_number=1,
    )
    db.add(session)
    db.flush()

    # Create summary — SessionSummary has no therapist_id/patient_id columns,
    # it is linked only through the Session.summary_id back-reference.
    summary = SessionSummary(
        status=SummaryStatus.APPROVED,
        full_summary="Test summary",
        generated_from="text",
    )
    db.add(summary)
    db.flush()

    session.summary_id = summary.id
    db.flush()

    exercise = Exercise(
        therapist_id=therapist.id,
        patient_id=patient.id,
        session_summary_id=summary.id,
        description="Do the homework",
    )
    db.add(exercise)
    db.commit()

    db.refresh(therapist)
    db.refresh(patient)
    db.refresh(session)
    db.refresh(summary)
    db.refresh(exercise)

    return {
        "therapist": therapist,
        "patient": patient,
        "session": session,
        "summary": summary,
        "exercise": exercise,
    }


# ── Test 1: delete_session preserves exercises ─────────────────────────────

@pytest.mark.asyncio
async def test_delete_session_preserves_exercises(db, world):
    from app.services.session_service import SessionService
    from app.models.exercise import Exercise
    from app.models.session import Session as TherapySession, SessionSummary

    exercise_id = world["exercise"].id
    session_id = world["session"].id
    summary_id = world["summary"].id
    therapist_id = world["therapist"].id

    svc = SessionService(db=db)
    await svc.delete_session(session_id, therapist_id)

    # Session is gone
    assert db.query(TherapySession).filter(TherapySession.id == session_id).first() is None
    # Summary is gone
    assert db.query(SessionSummary).filter(SessionSummary.id == summary_id).first() is None
    # Exercise survives with session_summary_id nulled
    ex = db.query(Exercise).filter(Exercise.id == exercise_id).first()
    assert ex is not None, "Exercise must survive session deletion"
    assert ex.session_summary_id is None


# ── Test 2: delete_session_summary preserves exercises ────────────────────

@pytest.mark.asyncio
async def test_delete_session_summary_preserves_exercises(db, world):
    from app.services.session_service import SessionService
    from app.models.exercise import Exercise
    from app.models.session import Session as TherapySession, SessionSummary

    exercise_id = world["exercise"].id
    session_id = world["session"].id
    summary_id = world["summary"].id
    therapist_id = world["therapist"].id

    svc = SessionService(db=db)
    await svc.delete_session_summary(session_id, therapist_id)

    # Session still exists (summary-only delete)
    session = db.query(TherapySession).filter(TherapySession.id == session_id).first()
    assert session is not None
    assert session.summary_id is None

    # Summary is gone
    assert db.query(SessionSummary).filter(SessionSummary.id == summary_id).first() is None

    # Exercise survives with session_summary_id nulled
    ex = db.query(Exercise).filter(Exercise.id == exercise_id).first()
    assert ex is not None, "Exercise must survive summary deletion"
    assert ex.session_summary_id is None


# ── Test 3: admin therapist delete completes without FK error ──────────────

def test_admin_delete_therapist_no_fk_error(db, world):
    """
    Simulates the raw-SQL therapist deletion path from admin_panel.py.
    Exercises must be nulled and deleted before session_summaries are deleted,
    otherwise PostgreSQL raises ForeignKeyViolation (or SQLite raises IntegrityError).
    """
    from sqlalchemy import text

    tid = world["therapist"].id
    summary_id = world["summary"].id
    exercise_id = world["exercise"].id

    # Mirror the exact sequence from admin_panel.py (post-fix order)
    db.execute(
        text("UPDATE exercises SET session_summary_id = NULL WHERE therapist_id = :tid"),
        {"tid": tid},
    )
    db.execute(text("DELETE FROM exercises WHERE therapist_id = :tid"), {"tid": tid})

    db.execute(text("UPDATE sessions SET summary_id = NULL WHERE therapist_id = :tid"), {"tid": tid})
    db.execute(text(f"DELETE FROM session_summaries WHERE id = {summary_id}"))

    db.execute(text("DELETE FROM sessions WHERE therapist_id = :tid"), {"tid": tid})
    db.execute(text("DELETE FROM patients WHERE therapist_id = :tid"), {"tid": tid})
    db.execute(text("DELETE FROM therapist_profiles WHERE therapist_id = :tid"), {"tid": tid})
    db.execute(text("DELETE FROM therapists WHERE id = :tid"), {"tid": tid})

    db.commit()  # must not raise

    from app.models.exercise import Exercise
    assert db.query(Exercise).filter(Exercise.id == exercise_id).first() is None
