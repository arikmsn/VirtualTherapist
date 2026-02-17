"""Session service - handles therapy sessions and summary generation"""

from typing import Optional, Dict, Any, List
from datetime import date
from sqlalchemy.orm import Session
from app.models.session import Session as TherapySession, SessionSummary, SessionType
from app.models.patient import Patient
from app.core.agent import TherapyAgent
from app.services.audit_service import AuditService
from loguru import logger


class SessionService:
    """Service for managing therapy sessions and generating summaries"""

    def __init__(self, db: Session):
        self.db = db
        self.audit_service = AuditService(db)

    async def create_session(
        self,
        therapist_id: int,
        patient_id: int,
        session_date: date,
        session_type: SessionType = SessionType.INDIVIDUAL,
        duration_minutes: Optional[int] = None
    ) -> TherapySession:
        """Create a new therapy session record"""

        # Verify patient belongs to therapist
        patient = self.db.query(Patient).filter(
            Patient.id == patient_id,
            Patient.therapist_id == therapist_id
        ).first()

        if not patient:
            raise ValueError("Patient not found or does not belong to this therapist")

        # Get session number
        session_count = self.db.query(TherapySession).filter(
            TherapySession.patient_id == patient_id
        ).count()

        session = TherapySession(
            therapist_id=therapist_id,
            patient_id=patient_id,
            session_date=session_date,
            session_type=session_type,
            duration_minutes=duration_minutes,
            session_number=session_count + 1
        )

        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)

        # Audit log
        await self.audit_service.log_action(
            user_id=therapist_id,
            user_type="therapist",
            action="create",
            resource_type="session",
            resource_id=session.id,
            action_details={
                "patient_id": patient_id,
                "session_date": str(session_date),
                "session_number": session.session_number
            }
        )

        logger.info(f"Created session {session.id} for patient {patient_id}")
        return session

    async def generate_summary_from_audio(
        self,
        session_id: int,
        audio_file_path: str,
        agent: TherapyAgent
    ) -> SessionSummary:
        """
        Generate session summary from audio recording
        Uses AI to transcribe and summarize in therapist's style
        """

        session = self.db.query(TherapySession).filter(TherapySession.id == session_id).first()
        if not session:
            raise ValueError("Session not found")

        # Transcribe audio
        logger.info(f"Transcribing audio for session {session_id}")
        transcript = await self.audio_service.transcribe_audio(audio_file_path)

        # Generate summary using AI agent
        summary_prompt = f"""
צור סיכום פגישה מהתמליל הבא בסגנון שלך האישי.

**תמליל הפגישה:**
{transcript}

אנא צור סיכום מובנה הכולל:
1. נושאים שנדונו
2. התערבויות שבוצעו
3. התקדמות המטופל
4. משימות בית שהוטלו
5. תוכנית לפגישה הבאה

הסיכום צריך להיות בסגנון הכתיבה האישי שלך.
"""

        summary_text = await agent.generate_response(summary_prompt, context={
            "session_number": session.session_number,
            "patient_id": session.patient_id
        })

        # Parse and structure the summary
        summary = await self._create_summary_from_text(
            session_id=session_id,
            summary_text=summary_text,
            generated_from="audio"
        )

        # Update session
        session.has_recording = True
        session.audio_file_path = audio_file_path
        session.summary_id = summary.id

        self.db.commit()

        logger.info(f"Generated summary from audio for session {session_id}")
        return summary

    async def generate_summary_from_text(
        self,
        session_id: int,
        therapist_notes: str,
        agent: TherapyAgent,
        therapist_id: int,
    ) -> SessionSummary:
        """
        Generate session summary from therapist's text notes.
        Uses AI agent to produce a structured JSON summary.
        """

        session = self.db.query(TherapySession).filter(
            TherapySession.id == session_id,
            TherapySession.therapist_id == therapist_id,
        ).first()
        if not session:
            raise ValueError("Session not found or does not belong to this therapist")

        result = await agent.generate_session_summary(
            notes=therapist_notes,
            context={
                "session_number": session.session_number,
                "patient_id": session.patient_id,
            },
        )

        summary = SessionSummary(
            full_summary=result.full_summary,
            topics_discussed=result.topics_discussed,
            interventions_used=result.interventions_used,
            patient_progress=result.patient_progress,
            homework_assigned=result.homework_assigned,
            next_session_plan=result.next_session_plan,
            mood_observed=result.mood_observed,
            risk_assessment=result.risk_assessment,
            generated_from="text",
            therapist_edited=False,
            approved_by_therapist=False,
        )

        self.db.add(summary)
        self.db.flush()  # get summary.id without full commit

        session.summary_id = summary.id
        self.db.commit()
        self.db.refresh(summary)

        await self.audit_service.log_action(
            user_id=therapist_id,
            user_type="therapist",
            action="generate",
            resource_type="session_summary",
            resource_id=summary.id,
            action_details={"session_id": session_id, "generated_from": "text"},
        )

        logger.info(f"Generated structured summary for session {session_id}")
        return summary

    async def get_summary(self, session_id: int, therapist_id: int) -> Optional[SessionSummary]:
        """Get the summary for a session, verifying therapist ownership."""

        session = self.db.query(TherapySession).filter(
            TherapySession.id == session_id,
            TherapySession.therapist_id == therapist_id,
        ).first()

        if not session:
            raise ValueError("Session not found or does not belong to this therapist")

        return session.summary

    async def approve_summary(self, session_id: int, therapist_id: int) -> SessionSummary:
        """Therapist approves the generated summary"""

        session = self.db.query(TherapySession).filter(
            TherapySession.id == session_id,
            TherapySession.therapist_id == therapist_id
        ).first()

        if not session or not session.summary:
            raise ValueError("Session or summary not found")

        summary = session.summary
        summary.approved_by_therapist = True

        self.db.commit()

        # Audit log
        await self.audit_service.log_action(
            user_id=therapist_id,
            user_type="therapist",
            action="approve",
            resource_type="session_summary",
            resource_id=summary.id
        )

        logger.info(f"Therapist approved summary {summary.id}")
        return summary

    async def edit_summary(
        self,
        session_id: int,
        therapist_id: int,
        edited_content: Dict[str, Any]
    ) -> SessionSummary:
        """Therapist edits the generated summary"""

        session = self.db.query(TherapySession).filter(
            TherapySession.id == session_id,
            TherapySession.therapist_id == therapist_id
        ).first()

        if not session or not session.summary:
            raise ValueError("Session or summary not found")

        summary = session.summary

        # Update fields
        for field, value in edited_content.items():
            if hasattr(summary, field):
                setattr(summary, field, value)

        summary.therapist_edited = True

        self.db.commit()

        logger.info(f"Therapist edited summary {summary.id}")
        return summary

    async def get_session(
        self,
        session_id: int,
        therapist_id: int,
    ) -> Optional[TherapySession]:
        """Get a single session by ID (verify ownership)"""

        return self.db.query(TherapySession).filter(
            TherapySession.id == session_id,
            TherapySession.therapist_id == therapist_id,
        ).first()

    async def get_patient_sessions(
        self,
        patient_id: int,
        therapist_id: int,
    ) -> List[TherapySession]:
        """Get all sessions for a patient (verify ownership)"""

        patient = self.db.query(Patient).filter(
            Patient.id == patient_id,
            Patient.therapist_id == therapist_id,
        ).first()

        if not patient:
            raise ValueError("Patient not found")

        return (
            self.db.query(TherapySession)
            .filter(TherapySession.patient_id == patient_id)
            .order_by(TherapySession.session_date.desc())
            .all()
        )

    async def get_therapist_sessions(
        self,
        therapist_id: int,
        limit: int = 50,
    ) -> List[TherapySession]:
        """Get recent sessions for a therapist"""

        return (
            self.db.query(TherapySession)
            .filter(TherapySession.therapist_id == therapist_id)
            .order_by(TherapySession.session_date.desc())
            .limit(limit)
            .all()
        )

    async def update_session(
        self,
        session_id: int,
        therapist_id: int,
        update_data: Dict[str, Any],
    ) -> TherapySession:
        """Update session details"""

        session = self.db.query(TherapySession).filter(
            TherapySession.id == session_id,
            TherapySession.therapist_id == therapist_id,
        ).first()

        if not session:
            raise ValueError("Session not found")

        protected = {"id", "created_at", "therapist_id", "patient_id"}
        for field, value in update_data.items():
            if field not in protected and hasattr(session, field):
                setattr(session, field, value)

        self.db.commit()
        self.db.refresh(session)

        await self.audit_service.log_action(
            user_id=therapist_id,
            user_type="therapist",
            action="update",
            resource_type="session",
            resource_id=session.id,
            action_details=update_data,
        )

        logger.info(f"Updated session {session_id}")
        return session
