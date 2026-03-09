"""
Treatment Plan 2.0 — two-call pipeline + Plan Drift Helper (Phase 7).

Architecture:
  TreatmentPlanPipeline:
    Call 1 (extraction): approved summaries + existing plan → plan_json  (deep model)
    Call 2 (rendering) : plan_json + therapist signature → formal Hebrew prose (deep model)

  DriftChecker:
    Single call (fast model): active plan + last 3 summaries → DriftResult

Source-of-truth: only approved_by_therapist=True summaries are ever used.
Goal/milestone IDs are preserved across plan updates so history is traceable.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from typing import TYPE_CHECKING, Optional

from loguru import logger

from app.ai.models import FlowType
from app.ai.router import ModelRouter

if TYPE_CHECKING:
    from app.ai.provider import AIProvider


# ── Dataclasses ───────────────────────────────────────────────────────────────

@dataclass
class TreatmentPlanInput:
    """All context needed to generate or update a treatment plan."""
    client_id: int
    therapist_id: int
    modality: str
    approved_summaries: list[dict]       # approved_by_therapist=True, oldest → newest
    therapist_profile: dict
    existing_plan: Optional[dict] = None  # if updating, pass current plan_json
    therapist_signature: Optional[str] = None  # inject_into_prompt() string


@dataclass
class TreatmentPlanResult:
    """Output of TreatmentPlanPipeline.run()."""
    plan_json: dict
    rendered_text: str
    version: int
    model_used: str
    tokens_used: int


@dataclass
class DriftResult:
    """Output of DriftChecker.check_drift()."""
    drift_score: float           # 0.0 = on track, 1.0 = completely off plan
    drift_flags: list[str]       # Hebrew descriptions of what is NOT being addressed
    on_track_items: list[str]    # Hebrew descriptions of what IS being addressed
    recommendation: str          # one Hebrew sentence for the therapist


# ── Treatment plan JSON schema ─────────────────────────────────────────────────

TREATMENT_PLAN_JSON_SCHEMA: dict = {
    "presenting_problem": "",
    "focus_areas": [],
    "primary_goals": [
        {
            "goal_id": "G1",
            "description": "",
            "priority": "high | medium | low",
            "status": "not_started | in_progress | achieved | dropped",
            "target_sessions": 0,
        }
    ],
    "interventions_planned": [
        {
            "intervention": "",
            "linked_goal_ids": ["G1"],
            "frequency": "",
        }
    ],
    "milestones": [
        {
            "milestone_id": "M1",
            "description": "",
            "target_by_session": 0,
            "achieved": False,
        }
    ],
    "risk_considerations": [],
    "review_frequency_sessions": 6,
    "modality": "",
    "created_at_session": 0,
    "version": 1,
    "confidence": 0.0,
}

_SCHEMA_STR = json.dumps(TREATMENT_PLAN_JSON_SCHEMA, ensure_ascii=False, indent=2)

# ── Zero-summary fallback ─────────────────────────────────────────────────────

_ZERO_APPROVED_HEBREW = (
    "לא קיימים סיכומים מאושרים עבור לקוח זה. "
    "לא ניתן להפיק תוכנית טיפול ללא לפחות סיכום אחד מאושר."
)


# ── Drift threshold constants ─────────────────────────────────────────────────

_DRIFT_SOFT_THRESHOLD = 0.3    # above this → soft flag (store)
_DRIFT_HARD_THRESHOLD = 0.6    # above this → hard flag (⚠️ prefix)


# ── Prompt builders ───────────────────────────────────────────────────────────

_CBT_PLAN_ADDON = """\
## תכנית טיפולית במבנה CBT (פעיל):
- primary_goals: כל מטרה חייבת לכלול יעד קוגניטיבי ו/או התנהגותי ספציפי
  (לדוגמה: "הפחתת קטסטרופיזציה בנושא X", "פיתוח כלי תגובה להפחתת הימנעות")
- interventions_planned: חייב להכיל לפחות: ניסוי התנהגותי, בחינת עדויות, ויומן מחשבות
- milestones: כלול אבני דרך CBT ספציפיות (השלמת מטלות בית, שינוי בדירוג עצמי)
- risk_considerations: כלול הערה על דפוסי הימנעות אם קיימים
"""


def _build_extraction_system_prompt(inp: TreatmentPlanInput) -> str:
    is_update = inp.existing_plan is not None
    mode_note = (
        "You are UPDATING an existing treatment plan. "
        "CRITICAL rules for updates:\n"
        "- Preserve all existing goal_id and milestone_id identifiers exactly.\n"
        "- Update 'status' fields based on evidence from the session summaries.\n"
        "- Add new goals only if clearly warranted by the summaries.\n"
        "- Never silently remove goals — if a goal is no longer pursued, "
        "set its status to 'dropped'.\n"
        "- Increment the 'version' field by 1.\n"
        if is_update
        else (
            "You are CREATING a new treatment plan. "
            "Assign sequential goal IDs (G1, G2, …) and milestone IDs (M1, M2, …)."
        )
    )
    cbt_block = f"\n\n{_CBT_PLAN_ADDON.strip()}" if inp.modality.lower() == "cbt" else ""
    return "\n".join([
        "You are a clinical treatment planning assistant.",
        "Your ONLY job is to extract a structured treatment plan from approved session summaries "
        "and return it as JSON.",
        "Return ONLY valid JSON — no prose, no markdown fences, no explanation.",
        "",
        mode_note,
        "",
        "IMPORTANT: Do not fabricate clinical information. "
        f"Extract only what is documented in the approved summaries.{cbt_block}",
    ])


def _build_extraction_user_prompt(inp: TreatmentPlanInput) -> str:
    today = str(date.today())
    parts = [
        f"Modality: {inp.modality}",
        f"Sessions available: {len(inp.approved_summaries)} approved summary(ies)",
        f"Date: {today}",
        "",
    ]

    if inp.therapist_profile:
        parts.append("Therapist profile:")
        parts.append(json.dumps(inp.therapist_profile, ensure_ascii=False, indent=2))
        parts.append("")

    if inp.existing_plan:
        parts.append("EXISTING PLAN (update this — preserve IDs, update statuses):")
        parts.append(json.dumps(inp.existing_plan, ensure_ascii=False, indent=2))
        parts.append("")

    parts.append("--- Approved session summaries (oldest → newest) ---")
    for i, s in enumerate(inp.approved_summaries, 1):
        date_str = str(s.get("session_date", ""))
        num = s.get("session_number", i)
        text = s.get("full_summary", "")[:3000]
        parts.append(f"\n[Session #{num} — {date_str}]\n{text}")
    parts.append("--- End of summaries ---")

    parts.append("")
    version = (inp.existing_plan.get("version", 1) + 1) if inp.existing_plan else 1
    session_count = len(inp.approved_summaries)
    parts.append(
        f"Fill the JSON schema below. Set version={version}. "
        f"Set created_at_session={session_count}. "
        "Set confidence to your confidence level (0.0–1.0). "
        "Populate focus_areas as a list of short Hebrew strings (2–5 words each) "
        "describing the primary therapeutic focus areas."
    )
    parts.append(f"\nJSON schema:\n{_SCHEMA_STR}")
    return "\n".join(parts)


_FORMAL_HEBREW_PLAN_RULE = """\
FORMAL HEBREW WRITING STANDARDS (mandatory):
- Write in professional Hebrew (עברית מקצועית)
- Use full sentences appropriate for a clinical treatment plan document
- Structure the document with clear headings per section
- Use clinical terminology in Hebrew
"""


_CBT_PLAN_RENDER_ADDON = """\
## מבנה תכנית טיפולית בסגנון CBT (פעיל):
- שלב כותרת "גישה טיפולית: CBT — טיפול קוגניטיבי-התנהגותי"
- תאר מטרות בשפה קוגניטיבית-התנהגותית ספציפית
- פרט התערבויות CBT מתוכננות (ניסויים התנהגותיים, בחינת עדויות, הומוורק קוגניטיבי)
- אבני דרך יכללו קריטריונים מדידים (לדוגמה: "הפחתת הימנעות ב-50%")
"""


def _build_render_system_prompt(inp: TreatmentPlanInput) -> str:
    cbt_block = f"\n{_CBT_PLAN_RENDER_ADDON.strip()}" if inp.modality.lower() == "cbt" else ""
    return "\n".join([
        "You are a clinical documentation specialist preparing a formal treatment plan.",
        "This document will be reviewed by the therapist and may be included in the patient file.",
        "",
        _FORMAL_HEBREW_PLAN_RULE,
        cbt_block,
        "Render a complete, readable Hebrew treatment plan document from the structured data.",
        "Include all goals, milestones, planned interventions, and risk considerations.",
        "Format clearly with section headings.",
    ])


def _build_render_user_prompt(inp: TreatmentPlanInput, plan_json: dict) -> str:
    return (
        "The structured treatment plan has been extracted. "
        "Render it as a formal Hebrew clinical treatment plan document.\n\n"
        f"Structured plan data:\n{json.dumps(plan_json, ensure_ascii=False, indent=2)}\n\n"
        "Write the complete treatment plan document in Hebrew now."
    )


# ── JSON parser ───────────────────────────────────────────────────────────────

def _parse_plan_json(raw: str) -> dict:
    """Parse extraction response into a dict. Falls back to empty scaffold on failure."""
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        parts = cleaned.split("```")
        cleaned = parts[1] if len(parts) > 1 else cleaned
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
    cleaned = cleaned.strip()

    try:
        data = json.loads(cleaned)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        logger.warning("TreatmentPlanPipeline: non-JSON response, returning empty scaffold")

    return {
        "presenting_problem": "",
        "primary_goals": [],
        "interventions_planned": [],
        "milestones": [],
        "risk_considerations": [],
        "review_frequency_sessions": 6,
        "modality": "",
        "created_at_session": 0,
        "version": 1,
        "confidence": 0.0,
    }


# ── TreatmentPlanPipeline ────────────────────────────────────────────────────

class TreatmentPlanPipeline:
    """
    Two-call LLM pipeline for treatment plan generation and updates.

    Both calls use FlowType.TREATMENT_PLAN → AI_DEEP_MODEL (cross-session synthesis).

    Call 1 (extraction): approved summaries → plan_json
    Call 2 (rendering) : plan_json → formal Hebrew treatment plan prose
    """

    def __init__(self, provider: "AIProvider") -> None:
        self.provider = provider
        self._router = ModelRouter()
        self._last_extraction_result = None
        self._last_render_result = None

    async def run(self, inp: TreatmentPlanInput) -> TreatmentPlanResult:
        """Execute both calls and return a TreatmentPlanResult."""
        if not inp.approved_summaries:
            return TreatmentPlanResult(
                plan_json={},
                rendered_text=_ZERO_APPROVED_HEBREW,
                version=1,
                model_used="none",
                tokens_used=0,
            )

        plan_json = await self._extract(inp)
        rendered_text = await self._render(inp, plan_json)

        extract_res = self._last_extraction_result
        render_res = self._last_render_result
        total_tokens = 0
        if extract_res:
            total_tokens += (extract_res.prompt_tokens or 0) + (extract_res.completion_tokens or 0)
        if render_res:
            total_tokens += (render_res.prompt_tokens or 0) + (render_res.completion_tokens or 0)

        version = plan_json.get("version", 1)
        if inp.existing_plan:
            version = inp.existing_plan.get("version", 1) + 1

        return TreatmentPlanResult(
            plan_json=plan_json,
            rendered_text=rendered_text,
            version=version,
            model_used=render_res.model_used if render_res else "unknown",
            tokens_used=total_tokens,
        )

    async def _extract(self, inp: TreatmentPlanInput) -> dict:
        """Call 1: extract plan_json from approved summaries (deep model)."""
        system_msg = _build_extraction_system_prompt(inp)
        user_msg = _build_extraction_user_prompt(inp)

        model_id, route_reason = self._router.resolve(FlowType.TREATMENT_PLAN)
        result = await self.provider.generate(
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg},
            ],
            model=model_id,
            flow_type=FlowType.TREATMENT_PLAN,
            route_reason=route_reason,
            max_tokens=4096,
        )
        self._last_extraction_result = result
        return _parse_plan_json(result.content)

    async def _render(self, inp: TreatmentPlanInput, plan_json: dict) -> str:
        """Call 2: render plan_json into formal Hebrew prose (deep model)."""
        system_msg = _build_render_system_prompt(inp)
        if inp.therapist_signature:
            system_msg = inp.therapist_signature + "\n\n" + system_msg
        user_msg = _build_render_user_prompt(inp, plan_json)

        model_id, route_reason = self._router.resolve(FlowType.TREATMENT_PLAN)
        result = await self.provider.generate(
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg},
            ],
            model=model_id,
            flow_type=FlowType.TREATMENT_PLAN,
            route_reason=route_reason,
            max_tokens=8192,
        )
        self._last_render_result = result
        return result.content


# ── Drift check prompt ────────────────────────────────────────────────────────

_DRIFT_SYSTEM_PROMPT = """\
You are reviewing whether recent therapy sessions are aligned with the patient's treatment plan.
Respond in JSON only — no markdown, no prose.

Assess alignment and return:
{
  "drift_score": <float 0.0–1.0>,
  "drift_flags": [<Hebrew strings — what is NOT being addressed per the plan>],
  "on_track_items": [<Hebrew strings — what IS being addressed per the plan>],
  "recommendation": "<one Hebrew sentence for the therapist>"
}

Scoring guidance:
  0.0 = sessions fully address plan goals
  0.3 = minor drift — most goals addressed, small gaps
  0.6 = significant drift — key goals being neglected
  1.0 = sessions have no connection to plan goals
"""


def _build_drift_user_prompt(active_plan: dict, recent_summaries: list[dict]) -> str:
    parts = [
        "TREATMENT PLAN:",
        json.dumps(active_plan, ensure_ascii=False, indent=2),
        "",
        f"RECENT SESSION SUMMARIES (last {len(recent_summaries)} approved):",
    ]
    for i, s in enumerate(recent_summaries, 1):
        date_str = str(s.get("session_date", ""))
        num = s.get("session_number", i)
        text = s.get("full_summary", "")[:2000]
        parts.append(f"\n[Session #{num} — {date_str}]\n{text}")
    parts.append("")
    parts.append(
        "Assess drift and return JSON with drift_score, drift_flags, "
        "on_track_items, and recommendation."
    )
    return "\n".join(parts)


def _parse_drift_json(raw: str) -> dict:
    """Parse drift check response. Falls back to safe defaults on failure."""
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        parts = cleaned.split("```")
        cleaned = parts[1] if len(parts) > 1 else cleaned
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
    cleaned = cleaned.strip()

    try:
        data = json.loads(cleaned)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        logger.warning("DriftChecker: non-JSON response, using safe defaults")

    return {
        "drift_score": 0.0,
        "drift_flags": [],
        "on_track_items": [],
        "recommendation": "לא ניתן לחשב סטייה כעת.",
    }


# ── DriftChecker ──────────────────────────────────────────────────────────────

class DriftChecker:
    """
    Detects drift between recent session content and the active treatment plan.

    Called after each approved summary (non-blocking, via asyncio.create_task).
    Uses the fast model — best-effort, never raises.

    Thresholds:
        0.0–0.3: on track — no action
        0.3–0.6: soft flag — store drift data, surface in UI (Phase 9)
        0.6–1.0: hard flag — store + prefix recommendation with ⚠️
    """

    def __init__(self, provider: "AIProvider") -> None:
        self.provider = provider
        self._router = ModelRouter()
        self._last_result = None

    async def check_drift(
        self,
        active_plan: dict,
        recent_summaries: list[dict],
        session_id: int,
    ) -> DriftResult:
        """
        Run a single fast-model call and return a DriftResult.

        Args:
            active_plan:       Current plan_json from the active TreatmentPlan.
            recent_summaries:  Last ≤3 approved session summaries (newest last).
            session_id:        The session that triggered this check (for logging).
        """
        try:
            model_id, route_reason = self._router.resolve(FlowType.PLAN_DRIFT_CHECK)
            result = await self.provider.generate(
                messages=[
                    {"role": "system", "content": _DRIFT_SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": _build_drift_user_prompt(active_plan, recent_summaries),
                    },
                ],
                model=model_id,
                flow_type=FlowType.PLAN_DRIFT_CHECK,
                route_reason=route_reason,
            )
            self._last_result = result
            data = _parse_drift_json(result.content)
        except Exception as exc:
            logger.warning(f"DriftChecker.check_drift session={session_id} failed: {exc!r}")
            return DriftResult(
                drift_score=0.0,
                drift_flags=[],
                on_track_items=[],
                recommendation="לא ניתן לחשב סטייה כעת.",
            )

        drift_score = float(data.get("drift_score", 0.0))
        drift_flags = list(data.get("drift_flags", []))
        on_track_items = list(data.get("on_track_items", []))
        recommendation = str(data.get("recommendation", ""))

        # Hard flag: prefix recommendation with ⚠️
        if drift_score >= _DRIFT_HARD_THRESHOLD and not recommendation.startswith("⚠️"):
            recommendation = "⚠️ " + recommendation

        return DriftResult(
            drift_score=drift_score,
            drift_flags=drift_flags,
            on_track_items=on_track_items,
            recommendation=recommendation,
        )
