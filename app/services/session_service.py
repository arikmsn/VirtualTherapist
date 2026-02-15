"""Session service - handles therapy sessions and summary generation"""

from typing import Optional, Dict, Any
from datetime import date
from sqlalchemy.orm import Session
from app.models.session import Session as TherapySession, SessionSummary, SessionType
from app.models.patient import Patient
from app.core.agent import TherapyAgent
from app.services.audit_service import AuditService
from app.services.audio_service import AudioService
from loguru import logger


class SessionService:
    """Service for managing therapy sessions and generating summaries"""

    def __init__(self, db: Session):
        self.db = db
        self.audit_service = AuditService(db)
        self.audio_service = AudioService()

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
        agent: TherapyAgent
    ) -> SessionSummary:
        """
        Generate session summary from therapist's text notes
        Uses AI to structure and format in therapist's style
        """

        session = self.db.query(TherapySession).filter(TherapySession.id == session_id).first()
        if not session:
            raise ValueError("Session not found")

        summary_prompt = f"""
צור סיכום פגישה מובנה מהרשימות הבאות בסגנון שלך האישי.

**רשימות המטפל:**
{therapist_notes}

אנא צור סיכום מובנה הכולל:
1. נושאים שנדונו
2. התערבויות שבוצעו
3. התקדמות המטופל
4. משימות בית שהוטלו
5. תוכנית לפגישה הבאה
"""

        summary_text = await agent.generate_response(summary_prompt, context={
            "session_number": session.session_number,
            "patient_id": session.patient_id
        })

        summary = await self._create_summary_from_text(
            session_id=session_id,
            summary_text=summary_text,
            generated_from="text"
        )

        session.summary_id = summary.id
        self.db.commit()

        logger.info(f"Generated summary from text for session {session_id}")
        return summary

    async def _create_summary_from_text(
        self,
        session_id: int,
        summary_text: str,
        generated_from: str
    ) -> SessionSummary:
        """Create a SessionSummary object from generated text"""

        # Parse the summary text into structured components
        # This is a simplified version - in production, use more sophisticated parsing
        summary = SessionSummary(
            full_summary=summary_text,
            generated_from=generated_from,
            therapist_edited=False,
            approved_by_therapist=False,
            topics_discussed=[],  # Would parse from text
            interventions_used=[],  # Would parse from text
            homework_assigned=[]  # Would parse from text
        )

        self.db.add(summary)
        self.db.commit()
        self.db.refresh(summary)

        return summary

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
