"""Session service - handles therapy sessions and summary generation"""

import asyncio
from typing import Optional, Dict, Any, List
from datetime import date, datetime, timedelta
from sqlalchemy.orm import Session, joinedload
from app.models.session import Session as TherapySession, SessionSummary, SessionType, SummaryStatus
from app.models.patient import Patient
from app.models.exercise import Exercise
from app.models.ai_log import AIGenerationLog
from app.core.agent import (
    TherapyAgent,
    PatientInsightResult,
    SessionPrepBriefResult,
    DeepSummaryResult,
    TreatmentPlanResult,
    TreatmentGoal,
)
from app.ai.models import FlowType
from app.ai.completeness import CompletenessChecker
from app.ai.summary_pipeline import SummaryInput, SummaryPipeline, compute_edit_distance
from app.ai.prep import PrepInput, PrepMode, PrepPipeline, PrepResult
from app.ai.signature import SignatureEngine, inject_into_prompt
from app.services.treatment_plan_service import TreatmentPlanService
from app.services.audit_service import AuditService
from app.security.encryption import decrypt_data
from app.core.ai_context import build_ai_context_for_patient
from loguru import logger


# Twilio Content Template SID for appointment reminders.
# Template variables: 1=patient name, 2=therapist name, 3=session date, 4=session time
APPOINTMENT_TEMPLATE_SID = "HX6975c9f8284208ae4b202035dac62c85"


async def send_appointment_reminder(session_id: int) -> None:
    """
    Send a WhatsApp appointment reminder for the given session.
    Opens its own DB session so it is safe to call from asyncio.create_task or APScheduler.

    Uses the same deliver_message() path as the Messages UI so the transport,
    status tracking, and audit trail are identical.  Best-effort: logs errors but
    never raises, so callers are never blocked.
    """
    from app.core.database import SessionLocal
    from app.models.therapist import Therapist
    from app.models.message import Message, MessageStatus, MessageDirection
    from app.services.message_service import MessageService

    db = SessionLocal()
    try:
        session = db.query(TherapySession).filter(TherapySession.id == session_id).first()
        if not session:
            logger.warning(f"[appt_reminder] session {session_id} not found — skip")
            return

        patient = db.query(Patient).filter(Patient.id == session.patient_id).first()
        therapist = db.query(Therapist).filter(Therapist.id == session.therapist_id).first()

        if not patient or not therapist:
            logger.warning(f"[appt_reminder] session {session_id}: patient/therapist missing — skip")
            return

        patient_name = (
            decrypt_data(patient.full_name_encrypted)
            if patient.full_name_encrypted else "מטופל"
        )
        session_date_str = session.session_date.strftime("%d.%m.%y")
        session_time_str = session.start_time.strftime("%H:%M") if session.start_time else "לא צוינה"
        content_text = (
            f"שלום {patient_name}, זוהי תזכורת לפגישתך עם {therapist.full_name} "
            f"בתאריך {session_date_str} בשעה {session_time_str}."
        )

        # ── Blocked paths: save a FAILED record and return ───────────────────
        # Note: allow_ai_contact is NOT checked here — the therapist explicitly
        # requested this reminder when creating the session.  deliver_message()
        # doesn't check it either, so we match that behaviour.
        if not patient.phone_encrypted:
            logger.info(f"[appt_reminder] session {session_id}: no phone — recording FAILED")
            _save_failed_record(
                db, therapist.id, patient.id, session_id,
                f"[הודעה לא נשלחה — אין מספר טלפון למטופל/ת] {content_text}",
            )
            return

        patient_phone = decrypt_data(patient.phone_encrypted)

        # ── Create Message record, then deliver via the same path as Messages UI ──
        msg_record = Message(
            therapist_id=therapist.id,
            patient_id=patient.id,
            direction=MessageDirection.TO_PATIENT,
            content=content_text,
            status=MessageStatus.APPROVED,   # ready to deliver
            requires_approval=False,
            generated_by_ai=False,
            message_type="appointment_reminder",
            related_session_id=session_id,
            channel="whatsapp",
            recipient_phone=patient_phone,
        )
        db.add(msg_record)
        db.flush()   # get msg_record.id without closing the transaction

        msg_svc = MessageService(db)
        delivered = await msg_svc.deliver_message(msg_record.id)
        # deliver_message already calls db.commit()

        sent = delivered and delivered.status == MessageStatus.SENT
        logger.info(
            f"[notify] session_created patient={patient.id} session={session_id} "
            f"sent={sent} msg_id={msg_record.id}"
        )

    except Exception as exc:
        logger.error(f"[appt_reminder] session {session_id}: unexpected error — {exc}")
        try:
            db.rollback()
        except Exception:
            pass
    finally:
        db.close()


def _save_failed_record(
    db,
    therapist_id: int,
    patient_id: int,
    session_id: int,
    content: str,
) -> None:
    """Persist a FAILED appointment_reminder record (best-effort, swallows DB errors)."""
    from app.models.message import Message, MessageStatus, MessageDirection
    try:
        rec = Message(
            therapist_id=therapist_id,
            patient_id=patient_id,
            direction=MessageDirection.TO_PATIENT,
            content=content,
            status=MessageStatus.FAILED,
            requires_approval=False,
            generated_by_ai=False,
            message_type="appointment_reminder",
            related_session_id=session_id,
            channel="whatsapp",
            recipient_phone="",
        )
        db.add(rec)
        db.commit()
    except Exception as exc:
        logger.error(f"[appt_reminder] failed to save FAILED record: {exc}")
        db.rollback()


class SessionService:
    """Service for managing therapy sessions and generating summaries"""

    def __init__(self, db: Session):
        self.db = db
        self.audit_service = AuditService(db)

    def _write_generation_log(
        self,
        *,
        therapist_id: int,
        flow_type: FlowType,
        agent: TherapyAgent,
        session_id: Optional[int] = None,
        session_summary_id: Optional[int] = None,
        modality_pack_id: Optional[int] = None,
        generation_result=None,  # Optional[GenerationResult]; defaults to agent._last_result
    ) -> None:
        """
        Best-effort: write a row to ai_generation_log.
        Pass generation_result explicitly to log a result other than agent._last_result
        (e.g. from the CompletenessChecker).
        Never raises — a logging failure must not block the main flow.
        """
        try:
            last = generation_result if generation_result is not None else agent._last_result
            if last is None:
                return
            log_row = AIGenerationLog(
                therapist_id=therapist_id,
                flow_type=flow_type.value,
                session_id=session_id,
                session_summary_id=session_summary_id,
                modality_pack_id=modality_pack_id,
                model_used=last.model_used,
                route_reason=last.route_reason,
                prompt_version="1.0",
                prompt_tokens=last.prompt_tokens,
                completion_tokens=last.completion_tokens,
                generation_ms=last.generation_ms,
            )
            self.db.add(log_row)
            self.db.flush()
        except Exception as exc:
            logger.warning(f"_write_generation_log failed (non-blocking): {exc}")

    async def create_session(
        self,
        therapist_id: int,
        patient_id: int,
        session_date: date,
        session_type: SessionType = SessionType.INDIVIDUAL,
        duration_minutes: Optional[int] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        notify_patient: bool = False,
    ) -> TherapySession:
        """Create a new therapy session record"""

        # Verify patient belongs to therapist
        patient = self.db.query(Patient).filter(
            Patient.id == patient_id,
            Patient.therapist_id == therapist_id
        ).first()

        if not patient:
            raise ValueError("Patient not found or does not belong to this therapist")

        # Get session number: use MAX to handle gaps from deleted sessions
        from sqlalchemy import func
        max_num = self.db.query(func.max(TherapySession.session_number)).filter(
            TherapySession.patient_id == patient_id
        ).scalar()

        session = TherapySession(
            therapist_id=therapist_id,
            patient_id=patient_id,
            session_date=session_date,
            start_time=start_time,
            end_time=end_time,
            session_type=session_type,
            duration_minutes=duration_minutes,
            session_number=(max_num or 0) + 1
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

        # ── Appointment reminders — only when therapist opted in ──────────────
        if notify_patient:
            # 1. Immediate confirmation (best-effort, does not block the response)
            asyncio.create_task(send_appointment_reminder(session.id))

            # 2. 24h-before reminder — only when a future start_time is provided
            if session.start_time:
                remind_at = session.start_time - timedelta(hours=24)
                if remind_at > datetime.now():
                    from app.core.scheduler import scheduler
                    scheduler.add_job(
                        send_appointment_reminder,
                        trigger="date",
                        run_date=remind_at,
                        args=[session.id],
                        id=f"appt_reminder_{session.id}",
                        replace_existing=True,
                    )
                    logger.info(
                        f"Scheduled 24h appointment reminder for session {session.id} at {remind_at}"
                    )

        return session

    async def _assemble_summary_input(
        self,
        session: TherapySession,
        raw_content: str,
        agent: TherapyAgent,
    ) -> SummaryInput:
        """
        Build a SummaryInput from session data and DB context.

        - last_approved_summary: only from rows where approved_by_therapist = True
        - open_tasks: exercises not yet completed for this patient
        """
        from sqlalchemy import desc
        from app.security.encryption import decrypt_data as _decrypt

        # Patient display name (best-effort — never raise)
        patient = self.db.query(Patient).filter(Patient.id == session.patient_id).first()
        client_name = "מטופל"
        if patient and patient.full_name_encrypted:
            try:
                client_name = _decrypt(patient.full_name_encrypted)
            except Exception:
                pass

        # Most recent approved summary for this patient (excluding the current session)
        last_approved_row = (
            self.db.query(SessionSummary)
            .join(TherapySession, TherapySession.summary_id == SessionSummary.id)
            .filter(
                TherapySession.patient_id == session.patient_id,
                TherapySession.id != session.id,
                SessionSummary.approved_by_therapist == True,  # noqa: E712
            )
            .order_by(desc(TherapySession.session_date))
            .first()
        )
        last_approved_text = last_approved_row.full_summary if last_approved_row else None

        # Open (incomplete) homework / exercises for this patient
        open_exercises = (
            self.db.query(Exercise)
            .filter(
                Exercise.patient_id == session.patient_id,
                Exercise.completed == False,  # noqa: E712
            )
            .all()
        )
        open_tasks = [e.description or "" for e in open_exercises if e.description]

        # Signature injection (Phase 6): prepend style guidance to rendering system prompt
        therapist_id = session.therapist_id
        sig_engine = SignatureEngine(self.db)
        sig_profile = await sig_engine.get_active_profile(therapist_id)
        signature_prompt = inject_into_prompt(sig_profile) if sig_profile else None

        # AI protocol context (Section 1 integration)
        from app.models.therapist import TherapistProfile as _TherapistProfile
        _profile = (
            self.db.query(_TherapistProfile)
            .filter(_TherapistProfile.therapist_id == therapist_id)
            .first()
        )
        ai_ctx = build_ai_context_for_patient(_profile, patient)

        return SummaryInput(
            raw_content=raw_content,
            client_name=client_name,
            session_number=session.session_number or 1,
            session_date=session.session_date,
            last_approved_summary=last_approved_text,
            open_tasks=open_tasks,
            modality_pack=agent.modality_pack,
            therapist_signature=signature_prompt,
            ai_context=ai_ctx,
        )

    async def generate_summary_from_audio(
        self,
        session_id: int,
        audio_bytes: bytes,
        filename: str,
        agent: TherapyAgent,
        therapist_id: int,
        language: str | None = None,
    ) -> SessionSummary:
        """
        PRD Golden Path: Record → Transcribe → Summarise → Review → Approve.

        1. Transcribe audio via AudioService (Whisper ASR).
        2. Feed transcript to agent.generate_session_summary (structured JSON).
        3. Store transcript *and* summary separately (PRD audit requirement).
        """
        from app.services.audio_service import AudioService

        session = self.db.query(TherapySession).filter(
            TherapySession.id == session_id,
            TherapySession.therapist_id == therapist_id,
        ).first()
        if not session:
            raise ValueError("Session not found or does not belong to this therapist")

        # Step 1 — ASR transcription
        audio_service = AudioService()
        logger.info(f"Transcribing audio for session {session_id}")
        transcript = await audio_service.transcribe_upload(
            file_bytes=audio_bytes,
            filename=filename,
            language=language,
        )

        # Step 2 — Summary 2.0: two-call pipeline (extraction → rendering)
        summary_input = await self._assemble_summary_input(
            session=session,
            raw_content=transcript,
            agent=agent,
        )
        pipeline = SummaryPipeline(agent)
        clinical_json_dict, rendered_text = await pipeline.run(summary_input)

        modality_pack = agent.modality_pack
        modality_pack_id = modality_pack.id if modality_pack else None
        ai_model = (
            pipeline._last_render_result.model_used if pipeline._last_render_result else None
        )
        ai_confidence = int(clinical_json_dict.get("confidence", 0.0) * 100)
        new_homework_val = clinical_json_dict.get("new_homework")
        homework_list = (
            [new_homework_val]
            if isinstance(new_homework_val, str) and new_homework_val
            else (new_homework_val if isinstance(new_homework_val, list) else [])
        )
        risk_notes = (clinical_json_dict.get("risk_assessment") or {}).get("notes")

        # Step 3 — Persist transcript + summary + AI metadata
        summary = SessionSummary(
            full_summary=rendered_text,
            topics_discussed=clinical_json_dict.get("key_themes", []),
            interventions_used=clinical_json_dict.get("interventions_used", []),
            patient_progress=clinical_json_dict.get("client_response", ""),
            homework_assigned=homework_list,
            next_session_plan=clinical_json_dict.get("next_session_focus"),
            mood_observed=clinical_json_dict.get("mood_observed"),
            risk_assessment=risk_notes,
            clinical_json=clinical_json_dict,
            transcript=transcript,
            generated_from="audio",
            therapist_edited=False,
            approved_by_therapist=False,
            ai_draft_text=rendered_text,   # rendered prose = what therapist sees and edits
            ai_model=ai_model,
            ai_prompt_version="2.0",
            ai_confidence=ai_confidence,
            modality_pack_id=modality_pack_id,
        )

        self.db.add(summary)
        self.db.flush()

        session.has_recording = True
        session.summary_id = summary.id
        self.db.flush()

        # Step 4 — Completeness check (fast model, best-effort)
        if agent.provider:
            checker = CompletenessChecker(agent.provider)
            completeness = await checker.check(
                summary_text=rendered_text,
                modality_pack=modality_pack,
            )
            summary.completeness_score = completeness.score if completeness.score >= 0 else None
            summary.completeness_data = completeness.to_dict()
            self.db.flush()
            self._write_generation_log(
                therapist_id=therapist_id,
                flow_type=FlowType.COMPLETENESS_CHECK,
                agent=agent,
                session_id=session.id,
                session_summary_id=summary.id,
                modality_pack_id=modality_pack_id,
                generation_result=checker._last_result,
            )

        # Log extraction call and render call separately
        self._write_generation_log(
            therapist_id=therapist_id,
            flow_type=FlowType.SESSION_SUMMARY,
            agent=agent,
            session_id=session.id,
            session_summary_id=summary.id,
            modality_pack_id=modality_pack_id,
            generation_result=pipeline._last_extraction_result,
        )
        self._write_generation_log(
            therapist_id=therapist_id,
            flow_type=FlowType.SESSION_SUMMARY,
            agent=agent,
            session_id=session.id,
            session_summary_id=summary.id,
            modality_pack_id=modality_pack_id,
            generation_result=pipeline._last_render_result,
        )

        self.db.commit()
        self.db.refresh(summary)

        await self.audit_service.log_action(
            user_id=therapist_id,
            user_type="therapist",
            action="generate",
            resource_type="session_summary",
            resource_id=summary.id,
            action_details={"session_id": session_id, "generated_from": "audio"},
        )

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
        PRD Golden Path (text variant): Notes → AI Structured Summary → Review → Approve.

        Uses the Summary 2.0 two-call pipeline:
          1. Extraction call  — structured JSON (clinical_json)
          2. Rendering call   — therapist-style Hebrew prose (full_summary)

        Completeness check runs after generation (fast model, best-effort).
        Updates or creates the SessionSummary row and links it to the session.
        Raises ValueError if the session is not found or not owned by this therapist.
        """

        session = self.db.query(TherapySession).filter(
            TherapySession.id == session_id,
            TherapySession.therapist_id == therapist_id,
        ).first()
        if not session:
            raise ValueError("Session not found or does not belong to this therapist")

        # Summary 2.0: two-call pipeline (extraction → rendering)
        summary_input = await self._assemble_summary_input(
            session=session,
            raw_content=therapist_notes,
            agent=agent,
        )
        pipeline = SummaryPipeline(agent)
        clinical_json_dict, rendered_text = await pipeline.run(summary_input)

        modality_pack = agent.modality_pack
        modality_pack_id = modality_pack.id if modality_pack else None
        ai_model = (
            pipeline._last_render_result.model_used if pipeline._last_render_result else None
        )
        ai_confidence = int(clinical_json_dict.get("confidence", 0.0) * 100)
        new_homework_val = clinical_json_dict.get("new_homework")
        homework_list = (
            [new_homework_val]
            if isinstance(new_homework_val, str) and new_homework_val
            else (new_homework_val if isinstance(new_homework_val, list) else [])
        )
        risk_notes = (clinical_json_dict.get("risk_assessment") or {}).get("notes")

        summary = SessionSummary(
            full_summary=rendered_text,
            topics_discussed=clinical_json_dict.get("key_themes", []),
            interventions_used=clinical_json_dict.get("interventions_used", []),
            patient_progress=clinical_json_dict.get("client_response", ""),
            homework_assigned=homework_list,
            next_session_plan=clinical_json_dict.get("next_session_focus"),
            mood_observed=clinical_json_dict.get("mood_observed"),
            risk_assessment=risk_notes,
            clinical_json=clinical_json_dict,
            generated_from="text",
            therapist_edited=False,
            approved_by_therapist=False,
            ai_draft_text=rendered_text,   # rendered prose = what therapist sees and edits
            ai_model=ai_model,
            ai_prompt_version="2.0",
            ai_confidence=ai_confidence,
            modality_pack_id=modality_pack_id,
        )

        self.db.add(summary)
        self.db.flush()

        session.summary_id = summary.id
        self.db.flush()

        # Completeness check (fast model, best-effort)
        if agent.provider:
            checker = CompletenessChecker(agent.provider)
            completeness = await checker.check(
                summary_text=rendered_text,
                modality_pack=modality_pack,
            )
            summary.completeness_score = completeness.score if completeness.score >= 0 else None
            summary.completeness_data = completeness.to_dict()
            self.db.flush()
            self._write_generation_log(
                therapist_id=therapist_id,
                flow_type=FlowType.COMPLETENESS_CHECK,
                agent=agent,
                session_id=session.id,
                session_summary_id=summary.id,
                modality_pack_id=modality_pack_id,
                generation_result=checker._last_result,
            )

        # Log extraction and render calls separately
        self._write_generation_log(
            therapist_id=therapist_id,
            flow_type=FlowType.SESSION_SUMMARY,
            agent=agent,
            session_id=session.id,
            session_summary_id=summary.id,
            modality_pack_id=modality_pack_id,
            generation_result=pipeline._last_extraction_result,
        )
        self._write_generation_log(
            therapist_id=therapist_id,
            flow_type=FlowType.SESSION_SUMMARY,
            agent=agent,
            session_id=session.id,
            session_summary_id=summary.id,
            modality_pack_id=modality_pack_id,
            generation_result=pipeline._last_render_result,
        )

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
        """
        Approve a session summary.

        Sets approved_by_therapist=True and status=APPROVED.
        Approved summaries become the source of truth for prep briefs, deep summaries,
        treatment plans, and the patient insight report.
        Raises ValueError if the session or summary is not found.
        """

        session = self.db.query(TherapySession).filter(
            TherapySession.id == session_id,
            TherapySession.therapist_id == therapist_id
        ).first()

        if not session or not session.summary:
            raise ValueError("Session or summary not found")

        summary = session.summary
        summary.approved_by_therapist = True

        # Compute edit distance: how much did the therapist change the AI draft?
        # ai_draft_text = rendered prose at generation time; full_summary = current (possibly edited) text
        if summary.ai_draft_text and summary.full_summary:
            try:
                summary.therapist_edit_distance = compute_edit_distance(
                    summary.ai_draft_text, summary.full_summary
                )
            except Exception:
                pass  # non-blocking — best effort

        self.db.commit()

        # Signature learning hook (Phase 6) — fire-and-forget, non-blocking
        if summary.ai_draft_text:
            try:
                import asyncio
                sig_engine = SignatureEngine(self.db)
                asyncio.create_task(
                    sig_engine.record_approval(
                        therapist_id=therapist_id,
                        session_id=session.id,
                        ai_draft=summary.ai_draft_text,
                        approved_text=summary.full_summary or "",
                        provider=None,   # no provider in approval path; rebuild deferred
                    )
                )
            except RuntimeError:
                # No running event loop (e.g. in tests) — call synchronously
                pass

        # Plan drift check hook (Phase 7) — fire-and-forget, non-blocking
        try:
            plan_service = TreatmentPlanService(self.db)
            asyncio.create_task(
                plan_service.run_drift_check(
                    patient_id=session.patient_id,
                    therapist_id=therapist_id,
                    session_id=session.id,
                    provider=None,  # no provider — no-op when provider=None
                )
            )
        except RuntimeError:
            pass  # no event loop in tests — skip silently

        # PatientTreatmentState rebuild hook (spec §6.3) — fire-and-forget, non-blocking
        try:
            from app.ai.state import rebuild_patient_treatment_state as _rebuild_pts
            asyncio.create_task(
                _rebuild_pts(
                    db=self.db,
                    patient_id=session.patient_id,
                    therapist_id=therapist_id,
                )
            )
        except RuntimeError:
            pass  # no event loop in tests — skip silently

        # Precompute hooks — fire-and-forget background jobs (spec D1, E1)
        # Each job creates its own DB session; safe to call here.
        try:
            from app.ai.precompute import (
                precompute_prep_for_patient,
                precompute_deep_summary_for_patient,
            )
            asyncio.create_task(precompute_prep_for_patient(session.patient_id))
            asyncio.create_task(precompute_deep_summary_for_patient(session.patient_id))
        except RuntimeError:
            pass  # no event loop in tests

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

    async def get_sessions_by_date(
        self,
        therapist_id: int,
        target_date: date,
    ) -> List[Dict[str, Any]]:
        """Get sessions for a therapist on a specific date, with patient names."""

        sessions = (
            self.db.query(TherapySession)
            .filter(
                TherapySession.therapist_id == therapist_id,
                TherapySession.session_date == target_date,
            )
            .order_by(TherapySession.start_time.asc().nullslast())
            .all()
        )

        # Batch-load summary statuses in one query
        summary_ids = [s.summary_id for s in sessions if s.summary_id]
        status_map: dict = {}
        if summary_ids:
            rows = self.db.query(
                SessionSummary.id,
                SessionSummary.status,
                SessionSummary.approved_by_therapist,
            ).filter(SessionSummary.id.in_(summary_ids)).all()
            for row in rows:
                status_map[row.id] = (
                    "approved" if row.approved_by_therapist else (row.status or "draft")
                )

        # Batch-load all patient names in one query (avoids N+1 per session)
        patient_ids = list({s.patient_id for s in sessions})
        patient_name_map: dict = {}
        if patient_ids:
            patient_rows = (
                self.db.query(Patient.id, Patient.full_name_encrypted)
                .filter(Patient.id.in_(patient_ids))
                .all()
            )
            for row in patient_rows:
                try:
                    patient_name_map[row.id] = decrypt_data(row.full_name_encrypted)
                except Exception:
                    patient_name_map[row.id] = row.full_name_encrypted or f"מטופל #{row.id}"

        results = []
        for s in sessions:
            patient_name = patient_name_map.get(s.patient_id, f"מטופל #{s.patient_id}")

            # Convert session_type enum to its string value for JSON serialisation
            session_type_value = (
                s.session_type.value if s.session_type else None
            )

            results.append({
                "id": s.id,
                "patient_id": s.patient_id,
                "patient_name": patient_name,
                "session_date": s.session_date,
                "start_time": s.start_time,
                "end_time": s.end_time,
                "session_type": session_type_value,
                "session_number": s.session_number,
                "has_summary": s.summary_id is not None,
                "summary_status": status_map.get(s.summary_id) if s.summary_id else None,
            })

        return results

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

    async def update_summary(
        self,
        session_id: int,
        therapist_id: int,
        updates: Dict[str, Any],
    ) -> SessionSummary:
        """Update (edit/approve) an existing session summary."""

        session = self.db.query(TherapySession).filter(
            TherapySession.id == session_id,
            TherapySession.therapist_id == therapist_id,
        ).first()

        if not session or not session.summary:
            raise ValueError("Session or summary not found")

        summary = session.summary

        # Allowed editable fields
        editable = {
            "full_summary", "topics_discussed", "interventions_used",
            "patient_progress", "homework_assigned", "next_session_plan",
            "mood_observed", "risk_assessment",
        }

        content_changed = False
        for field, value in updates.items():
            if field in editable and hasattr(summary, field):
                setattr(summary, field, value)
                content_changed = True

        if content_changed:
            summary.therapist_edited = True

        # Handle status change
        if "status" in updates:
            new_status = updates["status"]
            if new_status == "approved" or new_status == SummaryStatus.APPROVED:
                summary.status = SummaryStatus.APPROVED
                summary.approved_by_therapist = True
            elif new_status == "draft" or new_status == SummaryStatus.DRAFT:
                summary.status = SummaryStatus.DRAFT
                summary.approved_by_therapist = False

        self.db.commit()
        self.db.refresh(summary)

        # Precompute hooks — fire when the summary transitions to approved
        if summary.status == SummaryStatus.APPROVED:
            try:
                from app.ai.precompute import (
                    precompute_prep_for_patient,
                    precompute_deep_summary_for_patient,
                )
                asyncio.create_task(precompute_prep_for_patient(session.patient_id))
                asyncio.create_task(precompute_deep_summary_for_patient(session.patient_id))
            except RuntimeError:
                pass  # no event loop in tests

        action = "approve" if summary.status == SummaryStatus.APPROVED else "edit"
        await self.audit_service.log_action(
            user_id=therapist_id,
            user_type="therapist",
            action=action,
            resource_type="session_summary",
            resource_id=summary.id,
            action_details={"session_id": session_id},
        )

        logger.info(f"Updated summary {summary.id} (status={summary.status})")
        return summary

    async def get_patient_summaries(
        self,
        patient_id: int,
        therapist_id: int,
    ) -> List[Dict[str, Any]]:
        """Get all summaries for a patient's sessions, with session metadata."""

        patient = self.db.query(Patient).filter(
            Patient.id == patient_id,
            Patient.therapist_id == therapist_id,
        ).first()

        if not patient:
            raise ValueError("Patient not found")

        sessions = (
            self.db.query(TherapySession)
            .options(joinedload(TherapySession.summary))
            .filter(
                TherapySession.patient_id == patient_id,
                TherapySession.summary_id.isnot(None),
            )
            .order_by(TherapySession.session_date.desc())
            .all()
        )

        results = []
        for s in sessions:
            summary = s.summary
            if summary:
                results.append({
                    "session_id": s.id,
                    "session_date": s.session_date,
                    "session_number": s.session_number,
                    "summary": summary,
                })

        return results

    async def generate_patient_insight(
        self,
        patient_id: int,
        therapist_id: int,
        agent: TherapyAgent,
    ) -> PatientInsightResult:
        """Generate a cross-session AI insight report for a patient."""

        patient = self.db.query(Patient).filter(
            Patient.id == patient_id,
            Patient.therapist_id == therapist_id,
        ).first()

        if not patient:
            raise ValueError("Patient not found")

        # Fetch only approved summaries, ordered chronologically
        sessions = (
            self.db.query(TherapySession)
            .options(joinedload(TherapySession.summary))
            .filter(
                TherapySession.patient_id == patient_id,
                TherapySession.summary_id.isnot(None),
            )
            .order_by(TherapySession.session_date.asc())
            .all()
        )

        approved_summaries = []
        for s in sessions:
            summary = s.summary
            if summary and summary.status == SummaryStatus.APPROVED:
                approved_summaries.append({
                    "session_date": s.session_date,
                    "session_number": s.session_number,
                    "full_summary": summary.full_summary,
                    "topics_discussed": summary.topics_discussed,
                    "patient_progress": summary.patient_progress,
                    "risk_assessment": summary.risk_assessment,
                })
        approved_summaries = approved_summaries[-10:]  # last 10 — older sessions add noise

        if not approved_summaries:
            raise ValueError("אין סיכומים מאושרים עבור מטופל זה. יש לאשר לפחות סיכום אחד.")

        result = await agent.generate_patient_insight_summary(
            patient_name=patient.full_name_encrypted,  # display name
            summaries_timeline=approved_summaries,
        )

        await self.audit_service.log_action(
            user_id=therapist_id,
            user_type="therapist",
            action="generate",
            resource_type="patient_insight",
            resource_id=patient_id,
            action_details={"approved_summaries_count": len(approved_summaries)},
        )

        logger.info(f"Generated insight summary for patient {patient_id} ({len(approved_summaries)} summaries)")
        return result

    async def generate_prep_brief(
        self,
        session_id: int,
        therapist_id: int,
        agent: TherapyAgent,
        max_summaries: int = 5,
    ) -> SessionPrepBriefResult:
        """Generate a concise AI prep brief for an upcoming session."""

        session = self.db.query(TherapySession).filter(
            TherapySession.id == session_id,
            TherapySession.therapist_id == therapist_id,
        ).first()

        if not session:
            raise ValueError("Session not found or does not belong to this therapist")

        patient = self.db.query(Patient).filter(Patient.id == session.patient_id).first()
        if not patient:
            raise ValueError("Patient not found")

        # Fetch approved summaries for this patient, most recent last, limited
        patient_sessions = (
            self.db.query(TherapySession)
            .options(joinedload(TherapySession.summary))
            .filter(
                TherapySession.patient_id == session.patient_id,
                TherapySession.summary_id.isnot(None),
            )
            .order_by(TherapySession.session_date.asc())
            .all()
        )

        approved = []
        for s in patient_sessions:
            summary = s.summary
            if summary and summary.status == SummaryStatus.APPROVED:
                # Meeting prep must use the therapist-edited summary (full_summary),
                # not the original AI draft. full_summary is edited in-place.
                approved.append({
                    "session_date": s.session_date,
                    "session_number": s.session_number,
                    "full_summary": summary.full_summary,   # therapist-edited text
                    "topics_discussed": summary.topics_discussed,
                    "patient_progress": summary.patient_progress,
                    "homework_assigned": summary.homework_assigned,
                    "next_session_plan": summary.next_session_plan,
                    "risk_assessment": summary.risk_assessment,
                })

        # Keep only the last N approved summaries (graceful: proceed even with 0)
        recent = approved[-max_summaries:]

        # Fetch all open (incomplete) exercises for this patient
        open_exercises = (
            self.db.query(Exercise)
            .filter(
                Exercise.patient_id == session.patient_id,
                Exercise.therapist_id == therapist_id,
                Exercise.completed.is_(False),
            )
            .order_by(Exercise.created_at.asc())
            .all()
        )
        open_tasks = [
            {
                "description": ex.description,
                "created_at": str(ex.created_at)[:10] if ex.created_at else None,
            }
            for ex in open_exercises
        ]

        result = await agent.generate_session_prep_brief(
            patient_name=patient.full_name_encrypted,
            session_date=str(session.session_date),
            session_number=session.session_number,
            summaries_timeline=recent,
            open_tasks=open_tasks,
        )

        logger.info(f"Generated prep brief for session {session_id} ({len(recent)} summaries)")
        return result

    # ── Pre-Session Prep 2.0 (Phase 4) ───────────────────────────────────────

    _PREP_CACHE_SECONDS = 600   # fast-path: skip fingerprint check if age < 10 min
    _PREP_FRESH_SECONDS = 86_400  # 24 h — serve precomputed rendered_text within this window

    async def generate_prep_v2(
        self,
        session_id: int,
        therapist_id: int,
        mode: PrepMode,
        agent: "TherapyAgent",
    ) -> dict:
        """
        Generate a pre-session prep brief.  Three-tier cache (latency spec §D3):

        TIER 1 source=precomputed  — rendered_text fresh + fingerprint match → DB read only (~1 s)
        TIER 2 source=render_only  — prep_json exists, rendered_text stale → one LLM render call (~10–15 s)
        TIER 3 source=full_pipeline — no prep_json → extraction + render (~60–90 s, rare)

        SOURCE OF TRUTH: only summaries with approved_by_therapist=True are used.
        """
        from app.core.fingerprint import compute_fingerprint, FINGERPRINT_VERSION

        session = self.db.query(TherapySession).filter(
            TherapySession.id == session_id,
            TherapySession.therapist_id == therapist_id,
        ).first()
        if not session:
            raise ValueError("Session not found or does not belong to this therapist")

        patient = self.db.query(Patient).filter(Patient.id == session.patient_id).first()
        if not patient:
            raise ValueError("Patient not found")

        style_version = getattr(agent.profile, "style_version", 1) if agent.profile else 1

        # ── TIER 1: precomputed rendered text ─────────────────────────────────
        # Serve immediately if: same mode + rendered_text exists + within 24 h + fingerprint OK
        if (
            session.prep_rendered_text is not None
            and session.prep_json is not None
            and session.prep_mode == mode.value
            and session.prep_generated_at is not None
            and session.prep_input_fingerprint is not None
        ):
            age_seconds = (datetime.utcnow() - session.prep_generated_at).total_seconds()
            if age_seconds <= self._PREP_FRESH_SECONDS:
                # Fast path: skip fingerprint if age < 10 min (just generated / precomputed)
                if age_seconds < self._PREP_CACHE_SECONDS:
                    logger.warning(
                        f"[prep_v3] session={session_id} patient={session.patient_id} "
                        f"therapist={therapist_id} mode={mode.value} source=precomputed "
                        f"cache=hit reason=time age={age_seconds:.0f}s"
                    )
                    return self._prep_cache_response(session)

                # Full fingerprint check: re-verify inputs still match
                _approved_fp = self._load_approved_summaries_for_prep(session.patient_id)
                _fp = compute_fingerprint({
                    "mode": mode.value,
                    "summaries": [
                        {
                            "summary_id": s.get("summary_id"),
                            "approved_at": s.get("approved_at"),
                            "full_summary": s.get("full_summary"),
                        }
                        for s in _approved_fp
                    ],
                    "style_version": style_version,
                })
                if (
                    _fp == session.prep_input_fingerprint
                    and session.prep_input_fingerprint_version == FINGERPRINT_VERSION
                ):
                    logger.warning(
                        f"[prep_v3] session={session_id} patient={session.patient_id} "
                        f"therapist={therapist_id} mode={mode.value} source=precomputed "
                        f"cache=hit reason=fingerprint age={age_seconds:.0f}s"
                    )
                    return self._prep_cache_response(session)
                # Fingerprint mismatch → inputs changed → fall through to TIER 2

        # ── Shared setup (used by TIER 2 and TIER 3) ─────────────────────────
        approved_summaries = self._load_approved_summaries_for_prep(session.patient_id)

        modality_name = "generic_integrative"
        modality_prompt_module = None
        modality_pack = agent.modality_pack if hasattr(agent, "modality_pack") else None
        if modality_pack:
            modality_name = modality_pack.name
            modality_prompt_module = modality_pack.prompt_module

        sig_engine = SignatureEngine(self.db)
        sig_profile = await sig_engine.get_active_profile(therapist_id)

        ai_ctx = build_ai_context_for_patient(
            agent.profile if agent.profile else None,
            patient,
            session_count=len(approved_summaries),
        )

        from app.ai.context import build_llm_context_envelope_for_session
        from app.models.therapist import Therapist as _Therapist
        _therapist_obj = self.db.query(_Therapist).filter(_Therapist.id == therapist_id).first()
        summary_orms = self._load_approved_summary_orms(session.patient_id)
        _envelope_ok = False
        envelope = None
        try:
            envelope = build_llm_context_envelope_for_session(
                therapist=_therapist_obj,
                profile=agent.profile,
                signature=sig_profile,
                patient=patient,
                modality_pack=modality_pack,
                summaries=summary_orms,
                request_type="prep",
                request_mode=mode.value,
                extra={
                    "modality": modality_name,
                    "modality_prompt_module": modality_prompt_module,
                    "ai_context": ai_ctx,
                    "approved_sample_count": (
                        getattr(sig_profile, "approved_sample_count", 0) if sig_profile else 0
                    ),
                    "min_samples_required": (
                        getattr(sig_profile, "min_samples_required", 5) if sig_profile else 5
                    ),
                },
            )
            _envelope_ok = True
        except Exception as _env_exc:
            logger.warning(f"[prep_envelope] build failed, falling back to legacy: {_env_exc!r}")

        pipeline = PrepPipeline(agent)

        # ── TIER 2: render-only (extraction JSON exists, rendered_text stale) ─
        # Require prep_json.sessions_analyzed > 0 to avoid re-rendering a stale
        # empty scaffold (produced when the pipeline previously crashed).
        _prep_json_has_data = (
            session.prep_json is not None
            and session.prep_json.get("sessions_analyzed", 0) > 0
        )
        if _prep_json_has_data and envelope is not None:
            logger.warning(
                f"[prep_v3] session={session_id} patient={session.patient_id} "
                f"therapist={therapist_id} mode={mode.value} source=render_only "
                f"sessions_analyzed={len(approved_summaries)} style_version={style_version} "
                f"envelope_ok={_envelope_ok}"
            )
            result: PrepResult = await pipeline.render_only(envelope, session.prep_json)

        # ── TIER 3: full pipeline (no extraction JSON — cold start / new session) ─
        else:
            logger.warning(
                f"[prep_v3] session={session_id} patient={session.patient_id} "
                f"therapist={therapist_id} mode={mode.value} source=full_pipeline "
                f"sessions_analyzed={len(approved_summaries)} style_version={style_version} "
                f"envelope_ok={_envelope_ok}"
            )
            if envelope is not None:
                result = await pipeline.run_with_envelope(envelope)
            else:
                # Envelope build failed — legacy PrepInput path
                signature_prompt = inject_into_prompt(sig_profile) if sig_profile else None
                prep_inp = PrepInput(
                    client_id=session.patient_id,
                    session_id=session_id,
                    therapist_id=therapist_id,
                    mode=mode,
                    modality=modality_name,
                    approved_summaries=approved_summaries,
                    modality_prompt_module=modality_prompt_module,
                    therapist_signature=signature_prompt,
                    ai_context=ai_ctx,
                )
                result = await pipeline.run(prep_inp)

        # Completeness check (TIER 2 + 3 only — not for precomputed hits)
        if agent.provider and result.rendered_text and approved_summaries:
            checker = CompletenessChecker(agent.provider)
            completeness = await checker.check(
                summary_text=result.rendered_text,
                modality_pack=modality_pack,
            )
            result.completeness_score = completeness.score if completeness.score >= 0 else 0.0
            result.completeness_data = completeness.to_dict()
            self._write_generation_log(
                therapist_id=therapist_id,
                flow_type=FlowType.COMPLETENESS_CHECK,
                agent=agent,
                session_id=session_id,
                modality_pack_id=modality_pack.id if modality_pack else None,
                generation_result=checker._last_result,
            )

        # Persist
        session.prep_json = result.prep_json
        session.prep_rendered_text = result.rendered_text
        session.prep_mode = mode.value
        session.prep_completeness_score = result.completeness_score
        session.prep_completeness_data = result.completeness_data
        session.prep_generated_at = datetime.utcnow()
        session.prep_input_fingerprint = compute_fingerprint({
            "mode": mode.value,
            "summaries": [
                {
                    "summary_id": s.get("summary_id"),
                    "approved_at": s.get("approved_at"),
                    "full_summary": s.get("full_summary"),
                }
                for s in approved_summaries
            ],
            "style_version": style_version,
        })
        session.prep_input_fingerprint_version = FINGERPRINT_VERSION
        self.db.flush()

        # Telemetry
        self._write_generation_log(
            therapist_id=therapist_id,
            flow_type=FlowType.PRE_SESSION_PREP,
            agent=agent,
            session_id=session_id,
            modality_pack_id=modality_pack.id if modality_pack else None,
            generation_result=pipeline._last_extraction_result,
        )
        self._write_generation_log(
            therapist_id=therapist_id,
            flow_type=FlowType.PRE_SESSION_PREP,
            agent=agent,
            session_id=session_id,
            modality_pack_id=modality_pack.id if modality_pack else None,
            generation_result=pipeline._last_render_result,
        )

        logger.warning(
            f"[prep_v3] session={session_id} mode={mode.value} "
            f"sessions_analyzed={len(approved_summaries)} "
            f"tokens={result.tokens_used} completeness={result.completeness_score:.2f} "
            f"envelope_ok={_envelope_ok} done"
        )

        return {
            "rendered_text": result.rendered_text,
            "prep_json": result.prep_json,
            "mode": mode.value,
            "completeness_score": result.completeness_score,
            "sessions_analyzed": len(approved_summaries),
            "generated_at": session.prep_generated_at.isoformat(),
        }

    def _prep_cache_response(self, session: "TherapySession") -> dict:
        """Build a response dict from cached session data (no LLM call)."""
        prep_json = session.prep_json or {}
        return {
            "rendered_text": session.prep_rendered_text,
            "prep_json": prep_json,
            "mode": session.prep_mode,
            "completeness_score": session.prep_completeness_score,
            "sessions_analyzed": prep_json.get("sessions_analyzed", 0),
            "generated_at": session.prep_generated_at.isoformat() if session.prep_generated_at else None,
        }

    def _load_approved_summary_orms(
        self,
        patient_id: int,
        limit: int = 10,
    ) -> list:
        """
        Return the last *limit* approved SessionSummary ORM objects for *patient_id*,
        oldest → newest.

        Used by envelope builders (build_patient_treatment_state etc.) which need ORM
        objects rather than serialised dicts.  Same filter as _load_approved_summaries_for_prep.
        """
        patient_sessions = (
            self.db.query(TherapySession)
            .options(joinedload(TherapySession.summary))
            .filter(
                TherapySession.patient_id == patient_id,
                TherapySession.summary_id.isnot(None),
            )
            .order_by(TherapySession.session_date.asc())
            .all()
        )
        summaries = [
            s.summary
            for s in patient_sessions
            if s.summary and s.summary.approved_by_therapist
        ]
        return summaries[-limit:]

    def _load_approved_summaries_for_prep(
        self,
        patient_id: int,
        limit: int = 10,
    ) -> List[dict]:
        """
        Return the last *limit* approved summaries for *patient_id*, oldest → newest.

        SOURCE OF TRUTH: only rows where approved_by_therapist=True are included.
        Uses joinedload to avoid N+1 queries on the summary relationship.

        Shared by generate_prep_v2 (non-streaming) and stream_prep_v2 (streaming).
        """
        patient_sessions = (
            self.db.query(TherapySession)
            .options(joinedload(TherapySession.summary))
            .filter(
                TherapySession.patient_id == patient_id,
                TherapySession.summary_id.isnot(None),
            )
            .order_by(TherapySession.session_date.asc())
            .all()
        )
        result = []
        for s in patient_sessions:
            summary = s.summary
            if summary and summary.approved_by_therapist:
                result.append({
                    "summary_id": summary.id,
                    "approved_at": str(summary.edit_ended_at) if summary.edit_ended_at else None,
                    "session_date": str(s.session_date),
                    "session_number": s.session_number,
                    "full_summary": summary.full_summary,
                    "topics_discussed": summary.topics_discussed,
                    "homework_assigned": summary.homework_assigned,
                    "next_session_plan": summary.next_session_plan,
                    "risk_assessment": summary.risk_assessment,
                    "mood_observed": summary.mood_observed,
                    "clinical_json": summary.clinical_json,
                })
        return result[-limit:]

    async def delete_session(self, session_id: int, therapist_id: int) -> None:
        """
        Delete a session and its associated summary (if any).

        FK order: delete the session row first (drops the FK reference on sessions.summary_id),
        then delete the now-orphaned summary row.
        Raises ValueError if the session is not found or not owned by this therapist.
        """
        session = self.db.query(TherapySession).filter(
            TherapySession.id == session_id,
            TherapySession.therapist_id == therapist_id,
        ).first()
        if not session:
            raise ValueError("Session not found")

        summary_id = session.summary_id
        self.db.delete(session)
        self.db.flush()

        if summary_id:
            summary = self.db.query(SessionSummary).filter(
                SessionSummary.id == summary_id,
            ).first()
            if summary:
                self.db.delete(summary)

        self.db.commit()

        await self.audit_service.log_action(
            user_id=therapist_id,
            user_type="therapist",
            action="delete",
            resource_type="session",
            resource_id=session_id,
        )
        logger.info(f"Deleted session {session_id}")

    async def delete_session_summary(self, session_id: int, therapist_id: int) -> None:
        """
        Delete a session's AI-generated summary while keeping the session record.

        After deletion the session can receive a new summary via from-text or from-audio.
        Raises ValueError if the session or summary is not found.
        """
        session = self.db.query(TherapySession).filter(
            TherapySession.id == session_id,
            TherapySession.therapist_id == therapist_id,
        ).first()
        if not session:
            raise ValueError("Session not found")
        if not session.summary_id:
            raise ValueError("No summary to delete")

        summary_id = session.summary_id
        # Unlink FK before deleting the summary row
        session.summary_id = None
        self.db.flush()
        summary = self.db.query(SessionSummary).filter(
            SessionSummary.id == summary_id,
        ).first()
        if summary:
            self.db.delete(summary)
        self.db.commit()

        logger.info(f"Deleted summary for session {session_id}")

    def list_clips_for_session(self, session_id: int, therapist_id: int) -> list:
        """
        Return audio clips for a session, ordered by clip_index.
        Raises ValueError if the session is not found or not owned by this therapist.
        """
        from app.models.audio_clip import AudioClip

        session = self.db.query(TherapySession).filter(
            TherapySession.id == session_id,
            TherapySession.therapist_id == therapist_id,
        ).first()
        if not session:
            raise ValueError("Session not found")

        return (
            self.db.query(AudioClip)
            .filter(AudioClip.session_id == session_id)
            .order_by(AudioClip.clip_index.asc())
            .all()
        )

    def delete_clip(self, clip_id: int, session_id: int, therapist_id: int) -> None:
        """
        Delete a single audio clip and renumber subsequent clips to fill the gap.
        Raises ValueError if the clip is not found.
        """
        from app.models.audio_clip import AudioClip

        clip = self.db.query(AudioClip).filter(
            AudioClip.id == clip_id,
            AudioClip.session_id == session_id,
            AudioClip.therapist_id == therapist_id,
        ).first()
        if not clip:
            raise ValueError("Clip not found")

        deleted_index = clip.clip_index
        self.db.delete(clip)
        self.db.flush()

        # Re-number subsequent clips to fill the gap
        subsequent = (
            self.db.query(AudioClip)
            .filter(
                AudioClip.session_id == session_id,
                AudioClip.clip_index > deleted_index,
            )
            .all()
        )
        for c in subsequent:
            c.clip_index -= 1

        self.db.commit()

    def _build_patient_summary_context(
        self,
        patient_id: int,
        therapist_id: int,
    ):
        """
        Shared helper: return (patient, approved_summaries, all_tasks, metrics).
        Used by both generate_deep_summary and generate_treatment_plan_preview.
        """
        patient = self.db.query(Patient).filter(
            Patient.id == patient_id,
            Patient.therapist_id == therapist_id,
        ).first()
        if not patient:
            raise ValueError("Patient not found")

        all_sessions = (
            self.db.query(TherapySession)
            .options(joinedload(TherapySession.summary))
            .filter(TherapySession.patient_id == patient_id)
            .order_by(TherapySession.session_date.asc())
            .all()
        )

        approved_summaries = []
        for s in all_sessions:
            summary = s.summary
            if summary and summary.status == SummaryStatus.APPROVED:
                approved_summaries.append({
                    "session_date": s.session_date,
                    "session_number": s.session_number,
                    "full_summary": summary.full_summary,
                    "topics_discussed": summary.topics_discussed,
                    "patient_progress": summary.patient_progress,
                    "homework_assigned": summary.homework_assigned,
                    "risk_assessment": summary.risk_assessment,
                })
        approved_summaries = approved_summaries[-10:]  # last 10 — older sessions add noise

        exercises = (
            self.db.query(Exercise)
            .filter(
                Exercise.patient_id == patient_id,
                Exercise.therapist_id == therapist_id,
            )
            .order_by(Exercise.created_at.asc())
            .all()
        )
        all_tasks = [
            {
                "description": ex.description,
                "completed": ex.completed,
                "created_at": str(ex.created_at)[:10] if ex.created_at else None,
                "completed_at": str(ex.completed_at)[:10] if ex.completed_at else None,
                "session_summary_id": ex.session_summary_id,
            }
            for ex in exercises
        ]

        # Basic session metrics
        session_dates = [s.session_date for s in all_sessions if s.session_date]
        long_gaps = []
        for i in range(1, len(session_dates)):
            gap = (session_dates[i] - session_dates[i - 1]).days
            if gap > 30:
                long_gaps.append({
                    "from": str(session_dates[i - 1]),
                    "to": str(session_dates[i]),
                    "days": gap,
                })
        metrics = {
            "total_sessions": len(all_sessions),
            "first_session_date": str(session_dates[0]) if session_dates else None,
            "last_session_date": str(session_dates[-1]) if session_dates else None,
            "long_gaps": long_gaps,
        }

        return patient, approved_summaries, all_tasks, metrics

    async def generate_deep_summary(
        self,
        patient_id: int,
        therapist_id: int,
        agent: TherapyAgent,
    ) -> DeepSummaryResult:
        """Generate a comprehensive deep treatment summary from all approved data."""

        patient, approved_summaries, all_tasks, metrics = self._build_patient_summary_context(
            patient_id, therapist_id
        )

        if not approved_summaries:
            raise ValueError("אין סיכומים מאושרים עבור מטופל זה. יש לאשר לפחות סיכום אחד.")

        # Fingerprint-based cache: if inputs unchanged since last generation, skip AI call
        from app.core.fingerprint import compute_fingerprint, FINGERPRINT_VERSION
        from app.models.deep_summary import DeepSummary as _DeepSummary
        _fp = compute_fingerprint({
            "summaries": [s["full_summary"] for s in approved_summaries],
            "tasks": sorted(t["description"] for t in all_tasks),
        })
        # Expose fingerprint so the route can store it on the new DeepSummary row
        self._last_deep_summary_fingerprint = (_fp, FINGERPRINT_VERSION)
        _latest_ds = (
            self.db.query(_DeepSummary)
            .filter(
                _DeepSummary.patient_id == patient_id,
                _DeepSummary.therapist_id == therapist_id,
            )
            .order_by(_DeepSummary.created_at.desc())
            .first()
        )
        if (
            _latest_ds
            and _latest_ds.input_fingerprint == _fp
            and _latest_ds.input_fingerprint_version == FINGERPRINT_VERSION
            and _latest_ds.summary_json
        ):
            logger.info(
                f"[deep_summary] patient={patient_id} — fingerprint cache hit, skipping AI call"
            )
            sj = _latest_ds.summary_json
            return DeepSummaryResult(
                overall_treatment_picture=sj.get("overall_treatment_picture", ""),
                timeline_highlights=sj.get("timeline_highlights", []),
                goals_and_tasks=sj.get("goals_and_tasks", ""),
                measurable_progress=sj.get("measurable_progress", ""),
                directions_for_next_phase=sj.get("directions_for_next_phase", ""),
            )

        therapist_locale = (agent.profile.language if agent.profile else None) or "he"

        result = await agent.generate_deep_summary(
            patient_name=patient.full_name_encrypted,
            approved_summaries=approved_summaries,
            all_tasks=all_tasks,
            metrics=metrics,
            therapist_locale=therapist_locale,
        )

        # ── Sanity checks: trim AI over-reach relative to actual data ─────────
        approved_count = len(approved_summaries)
        task_count = len(all_tasks)

        # Cap timeline_highlights when very little data exists
        max_highlights = max(1, min(approved_count * 2, 6))
        if len(result.timeline_highlights) > max_highlights:
            logger.warning(
                f"deep_summary patient={patient_id}: AI returned "
                f"{len(result.timeline_highlights)} timeline items for "
                f"{approved_count} approved summaries — trimming to {max_highlights}"
            )
            result.timeline_highlights = result.timeline_highlights[:max_highlights]

        # If no tasks exist but goals_and_tasks looks task-specific, log for visibility
        if task_count == 0 and result.goals_and_tasks:
            logger.info(
                f"deep_summary patient={patient_id}: no tasks in DB — "
                f"goals_and_tasks should only reflect session focus areas"
            )

        await self.audit_service.log_action(
            user_id=therapist_id,
            user_type="therapist",
            action="generate",
            resource_type="patient_deep_summary",
            resource_id=patient_id,
            action_details={
                "approved_summaries_count": len(approved_summaries),
                "total_sessions": metrics["total_sessions"],
            },
        )

        logger.info(
            f"Generated deep summary for patient {patient_id} "
            f"({len(approved_summaries)} approved summaries)"
        )
        return result

    async def generate_treatment_plan_preview(
        self,
        patient_id: int,
        therapist_id: int,
        agent: TherapyAgent,
    ) -> TreatmentPlanResult:
        """Generate a treatment plan preview (goals, focus areas, interventions) from approved data."""

        patient, approved_summaries, all_tasks, _ = self._build_patient_summary_context(
            patient_id, therapist_id
        )

        therapist_locale = (agent.profile.language if agent.profile else None) or "he"

        result = await agent.generate_treatment_plan_preview(
            patient_name=patient.full_name_encrypted,
            approved_summaries=approved_summaries,
            all_tasks=all_tasks,
            therapist_locale=therapist_locale,
        )

        await self.audit_service.log_action(
            user_id=therapist_id,
            user_type="therapist",
            action="generate",
            resource_type="patient_treatment_plan_preview",
            resource_id=patient_id,
            action_details={"approved_summaries_count": len(approved_summaries)},
        )

        logger.info(f"Generated treatment plan preview for patient {patient_id}")
        return result
