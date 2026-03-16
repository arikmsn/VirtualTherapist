"""Treatment plan service — Phase 7: Treatment Plan 2.0 + Drift Helper."""

from datetime import datetime
from typing import Optional

from loguru import logger
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.ai.models import FlowType
from app.ai.treatment_plan import (
    DriftChecker,
    DriftResult,
    TreatmentPlanInput,
    TreatmentPlanPipeline,
    TreatmentPlanResult,
)
from app.ai.signature import SignatureEngine, inject_into_prompt
from app.models.ai_log import AIGenerationLog
from app.models.patient import Patient
from app.models.session import Session as TherapySession, SessionSummary
from app.models.therapist import Therapist, TherapistProfile
from app.models.treatment_plan import PlanStatus, TreatmentPlan
from app.core.ai_context import build_ai_context_for_patient


class TreatmentPlanService:
    """
    Business logic for treatment plans.

    Source-of-truth rule: only approved_by_therapist=True summaries are used.
    Never reads ai_draft_text or unapproved summary rows.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _fetch_approved_summaries(
        self,
        patient_id: int,
        therapist_id: int,
        session_ids: Optional[list[int]] = None,
    ) -> list[dict]:
        """
        Return approved summary dicts for a patient, oldest → newest.
        SOURCE OF TRUTH: approved_by_therapist=True only.
        """
        query = (
            self.db.query(TherapySession)
            .options(joinedload(TherapySession.summary))
            .filter(
                TherapySession.patient_id == patient_id,
                TherapySession.therapist_id == therapist_id,
                TherapySession.summary_id.isnot(None),
            )
            .order_by(TherapySession.session_date.asc())
        )
        if session_ids:
            query = query.filter(TherapySession.id.in_(session_ids))

        summaries = []
        for s in query.all():
            summary = s.summary
            if summary and summary.approved_by_therapist:
                summaries.append({
                    "session_date": str(s.session_date),
                    "session_number": s.session_number,
                    "full_summary": summary.full_summary,
                    "topics_discussed": summary.topics_discussed,
                    "homework_assigned": summary.homework_assigned,
                    "next_session_plan": summary.next_session_plan,
                    "risk_assessment": summary.risk_assessment,
                    "mood_observed": summary.mood_observed,
                })
        return summaries

    def _fetch_recent_approved_summaries(
        self,
        patient_id: int,
        therapist_id: int,
        limit: int = 3,
    ) -> list[dict]:
        """Return the most recent `limit` approved summaries (newest → oldest), reversed to oldest→newest."""
        query = (
            self.db.query(TherapySession)
            .options(joinedload(TherapySession.summary))
            .filter(
                TherapySession.patient_id == patient_id,
                TherapySession.therapist_id == therapist_id,
                TherapySession.summary_id.isnot(None),
            )
            .order_by(TherapySession.session_date.desc())
        )
        summaries = []
        for s in query.all():
            if len(summaries) >= limit:
                break
            summary = s.summary
            if summary and summary.approved_by_therapist:
                summaries.append({
                    "session_date": str(s.session_date),
                    "session_number": s.session_number,
                    "full_summary": summary.full_summary,
                    "topics_discussed": summary.topics_discussed,
                    "risk_assessment": summary.risk_assessment,
                    "mood_observed": summary.mood_observed,
                })
        return list(reversed(summaries))  # oldest → newest

    def _build_therapist_profile_dict(self, therapist_id: int) -> dict:
        therapist = self.db.query(Therapist).filter(Therapist.id == therapist_id).first()
        profile = (
            self.db.query(TherapistProfile)
            .filter(TherapistProfile.therapist_id == therapist_id)
            .first()
        )
        return {
            "name": therapist.full_name if therapist else "",
            "license_type": profile.certifications if profile else "",
            "modality": profile.therapeutic_approach.value if (profile and profile.therapeutic_approach) else "",
            "education": profile.education if profile else "",
        }

    def _next_plan_version(self, patient_id: int, therapist_id: int) -> int:
        """Return MAX(version)+1 across ALL plan rows for this patient (including archived/deleted)."""
        max_ver = (
            self.db.query(func.max(TreatmentPlan.version))
            .filter(
                TreatmentPlan.patient_id == patient_id,
                TreatmentPlan.therapist_id == therapist_id,
            )
            .scalar()
        )
        return (max_ver or 0) + 1

    def _get_active_plan(self, patient_id: int, therapist_id: int) -> Optional[TreatmentPlan]:
        return (
            self.db.query(TreatmentPlan)
            .filter(
                TreatmentPlan.patient_id == patient_id,
                TreatmentPlan.therapist_id == therapist_id,
                TreatmentPlan.status == PlanStatus.ACTIVE.value,
            )
            .order_by(TreatmentPlan.version.desc())
            .first()
        )

    def _write_generation_log(
        self,
        *,
        therapist_id: int,
        flow_type: FlowType,
        patient_id: int,
        plan_id: Optional[int] = None,
        generation_result=None,
        drift_score: Optional[float] = None,
        extra_notes: str = "",
    ) -> None:
        """Best-effort telemetry. Never raises."""
        try:
            if generation_result is None:
                return
            log_row = AIGenerationLog(
                therapist_id=therapist_id,
                flow_type=flow_type.value,
                session_id=None,
                session_summary_id=None,
                modality_pack_id=None,
                model_used=generation_result.model_used,
                route_reason=generation_result.route_reason,
                prompt_version="7.0",
                prompt_tokens=generation_result.prompt_tokens,
                completion_tokens=generation_result.completion_tokens,
                generation_ms=generation_result.generation_ms,
                completeness_score=drift_score,
            )
            self.db.add(log_row)
            self.db.flush()
        except Exception as exc:
            logger.warning(f"treatment_plan _write_generation_log failed (non-blocking): {exc}")

    # ── Core operations ───────────────────────────────────────────────────────

    async def create_plan(
        self,
        patient_id: int,
        therapist_id: int,
        session_ids: Optional[list[int]],
        provider,  # AIProvider
    ) -> TreatmentPlan:
        """
        Generate and persist a new treatment plan (version 1).

        Returns the saved TreatmentPlan ORM object (status=active).
        """
        patient = self.db.query(Patient).filter(
            Patient.id == patient_id,
            Patient.therapist_id == therapist_id,
        ).first()
        if not patient:
            raise ValueError("Patient not found or does not belong to this therapist")

        # Archive any existing active plan before creating new one
        existing = self._get_active_plan(patient_id, therapist_id)
        if existing:
            raise ValueError(
                "An active treatment plan already exists. "
                "Use PUT to update it or archive it first."
            )

        approved_summaries = self._fetch_approved_summaries(
            patient_id=patient_id,
            therapist_id=therapist_id,
            session_ids=session_ids,
        )
        therapist_profile = self._build_therapist_profile_dict(therapist_id)
        modality = therapist_profile.get("modality", "")

        # Signature injection
        sig_engine = SignatureEngine(self.db)
        sig_profile = await sig_engine.get_active_profile(therapist_id)
        signature_prompt = inject_into_prompt(sig_profile) if sig_profile else None

        # AI protocol context
        _profile_orm = (
            self.db.query(TherapistProfile)
            .filter(TherapistProfile.therapist_id == therapist_id)
            .first()
        )
        ai_ctx = build_ai_context_for_patient(_profile_orm, patient, session_count=len(approved_summaries))

        # Compute version BEFORE the AI call so we don't hold a DB query open after a long await
        next_version = self._next_plan_version(patient_id, therapist_id)

        inp = TreatmentPlanInput(
            client_id=patient_id,
            therapist_id=therapist_id,
            modality=modality,
            approved_summaries=approved_summaries,
            therapist_profile=therapist_profile,
            existing_plan=None,
            therapist_signature=signature_prompt,
            ai_context=ai_ctx,
        )

        pipeline = TreatmentPlanPipeline(provider)
        result: TreatmentPlanResult = await pipeline.run(inp)

        plan = TreatmentPlan(
            patient_id=patient_id,
            therapist_id=therapist_id,
            status=PlanStatus.ACTIVE.value,
            plan_json=result.plan_json,
            rendered_text=result.rendered_text,
            version=next_version,
            parent_version_id=None,
            model_used=result.model_used,
            tokens_used=result.tokens_used,
        )
        self.db.add(plan)
        self.db.flush()

        # Telemetry — extraction + render
        self._write_generation_log(
            therapist_id=therapist_id,
            flow_type=FlowType.TREATMENT_PLAN,
            patient_id=patient_id,
            plan_id=plan.id,
            generation_result=pipeline._last_extraction_result,
        )
        self._write_generation_log(
            therapist_id=therapist_id,
            flow_type=FlowType.TREATMENT_PLAN,
            patient_id=patient_id,
            plan_id=plan.id,
            generation_result=pipeline._last_render_result,
        )

        logger.info(
            f"[treatment_plan] CREATE patient={patient_id} version={next_version} "
            f"summaries={len(approved_summaries)} tokens={result.tokens_used} plan_id={plan.id}"
        )
        return plan

    async def update_plan(
        self,
        patient_id: int,
        therapist_id: int,
        session_ids: Optional[list[int]],
        provider,
    ) -> TreatmentPlan:
        """
        Update the active treatment plan (creates new version, archives old).

        Returns the new TreatmentPlan ORM object.
        """
        patient = self.db.query(Patient).filter(
            Patient.id == patient_id,
            Patient.therapist_id == therapist_id,
        ).first()
        if not patient:
            raise ValueError("Patient not found or does not belong to this therapist")

        existing = self._get_active_plan(patient_id, therapist_id)
        if not existing:
            raise ValueError("No active treatment plan found. Use POST to create one.")

        approved_summaries = self._fetch_approved_summaries(
            patient_id=patient_id,
            therapist_id=therapist_id,
            session_ids=session_ids,
        )
        therapist_profile = self._build_therapist_profile_dict(therapist_id)
        modality = therapist_profile.get("modality", "")

        sig_engine = SignatureEngine(self.db)
        sig_profile = await sig_engine.get_active_profile(therapist_id)
        signature_prompt = inject_into_prompt(sig_profile) if sig_profile else None

        # AI protocol context
        _profile_orm = (
            self.db.query(TherapistProfile)
            .filter(TherapistProfile.therapist_id == therapist_id)
            .first()
        )
        ai_ctx = build_ai_context_for_patient(_profile_orm, patient, session_count=len(approved_summaries))

        # Compute version BEFORE the AI call so we don't hold a DB query open after a long await
        next_version = self._next_plan_version(patient_id, therapist_id)

        inp = TreatmentPlanInput(
            client_id=patient_id,
            therapist_id=therapist_id,
            modality=modality,
            approved_summaries=approved_summaries,
            therapist_profile=therapist_profile,
            existing_plan=existing.plan_json,
            therapist_signature=signature_prompt,
            ai_context=ai_ctx,
        )

        pipeline = TreatmentPlanPipeline(provider)
        result: TreatmentPlanResult = await pipeline.run(inp)

        # Archive old plan
        existing.status = PlanStatus.ARCHIVED.value

        new_plan = TreatmentPlan(
            patient_id=patient_id,
            therapist_id=therapist_id,
            status=PlanStatus.ACTIVE.value,
            plan_json=result.plan_json,
            rendered_text=result.rendered_text,
            version=next_version,
            parent_version_id=existing.id,
            model_used=result.model_used,
            tokens_used=result.tokens_used,
        )
        self.db.add(new_plan)
        self.db.flush()

        self._write_generation_log(
            therapist_id=therapist_id,
            flow_type=FlowType.TREATMENT_PLAN,
            patient_id=patient_id,
            plan_id=new_plan.id,
            generation_result=pipeline._last_extraction_result,
        )
        self._write_generation_log(
            therapist_id=therapist_id,
            flow_type=FlowType.TREATMENT_PLAN,
            patient_id=patient_id,
            plan_id=new_plan.id,
            generation_result=pipeline._last_render_result,
        )

        logger.info(
            f"[treatment_plan] UPDATE patient={patient_id} version={next_version} "
            f"parent={existing.id} tokens={result.tokens_used} plan_id={new_plan.id}"
        )
        return new_plan

    def get_active_plan(self, patient_id: int, therapist_id: int) -> Optional[TreatmentPlan]:
        """Return the current active plan, or None."""
        patient = self.db.query(Patient).filter(
            Patient.id == patient_id,
            Patient.therapist_id == therapist_id,
        ).first()
        if not patient:
            raise ValueError("Patient not found or does not belong to this therapist")
        return self._get_active_plan(patient_id, therapist_id)

    def get_plan_history(self, patient_id: int, therapist_id: int) -> list[TreatmentPlan]:
        """Return all plan versions for a patient, newest first."""
        patient = self.db.query(Patient).filter(
            Patient.id == patient_id,
            Patient.therapist_id == therapist_id,
        ).first()
        if not patient:
            raise ValueError("Patient not found or does not belong to this therapist")
        return (
            self.db.query(TreatmentPlan)
            .filter(
                TreatmentPlan.patient_id == patient_id,
                TreatmentPlan.therapist_id == therapist_id,
            )
            .order_by(TreatmentPlan.version.desc())
            .all()
        )

    def approve_plan(self, plan_id: int, therapist_id: int) -> TreatmentPlan:
        """Set approved_at on a plan. Raises ValueError if not found or wrong owner."""
        plan = self.db.query(TreatmentPlan).filter(
            TreatmentPlan.id == plan_id,
            TreatmentPlan.therapist_id == therapist_id,
        ).first()
        if not plan:
            raise ValueError("Treatment plan not found or does not belong to this therapist")
        plan.approved_at = datetime.utcnow()
        self.db.flush()
        return plan

    def delete_plan(self, plan_id: int, therapist_id: int) -> None:
        """Hard-delete a treatment plan version. Raises ValueError if not found or wrong owner."""
        plan = self.db.query(TreatmentPlan).filter(
            TreatmentPlan.id == plan_id,
            TreatmentPlan.therapist_id == therapist_id,
        ).first()
        if not plan:
            raise ValueError("Treatment plan not found or does not belong to this therapist")
        self.db.delete(plan)
        self.db.flush()

    async def run_drift_check(
        self,
        patient_id: int,
        therapist_id: int,
        session_id: int,
        provider,
    ) -> Optional[DriftResult]:
        """
        Run drift check for a patient's active plan.

        Updates plan.drift_score / plan.drift_flags and session.plan_drift_score.
        Returns DriftResult, or None if no active plan exists.
        Non-blocking: never raises.
        """
        try:
            if provider is None:
                return None  # no provider available (e.g. called from hook without agent)

            active_plan = self._get_active_plan(patient_id, therapist_id)
            if not active_plan or not active_plan.plan_json:
                return None

            recent_summaries = self._fetch_recent_approved_summaries(
                patient_id=patient_id,
                therapist_id=therapist_id,
                limit=3,
            )
            if not recent_summaries:
                return None

            checker = DriftChecker(provider)
            drift = await checker.check_drift(
                active_plan=active_plan.plan_json,
                recent_summaries=recent_summaries,
                session_id=session_id,
            )

            # Persist drift data to plan
            active_plan.drift_score = drift.drift_score
            active_plan.drift_flags = drift.drift_flags
            active_plan.last_drift_check_at = datetime.utcnow()

            # Persist per-session drift score
            session = self.db.query(TherapySession).filter(
                TherapySession.id == session_id
            ).first()
            if session:
                session.plan_drift_checked = True
                session.plan_drift_score = drift.drift_score

            self.db.flush()

            # Telemetry
            self._write_generation_log(
                therapist_id=therapist_id,
                flow_type=FlowType.PLAN_DRIFT_CHECK,
                patient_id=patient_id,
                generation_result=checker._last_result,
                drift_score=drift.drift_score,
            )

            logger.info(
                f"[drift_check] patient={patient_id} session={session_id} "
                f"score={drift.drift_score:.2f} flags={len(drift.drift_flags)}"
            )
            return drift

        except Exception as exc:
            logger.warning(f"run_drift_check patient={patient_id} failed (non-blocking): {exc!r}")
            return None
