"""
Israeli Formal Record Support — two-call pipeline (Phase 5).

Architecture:
  Call 1 (extraction): approved summaries + record_type → record_json (deep model, always)
  Call 2 (rendering) : record_json + therapist_profile → formal Hebrew prose (deep model)

All formal records use FlowType.FORMAL_RECORD → AI_DEEP_MODEL.
High-stakes documentation: never fast or standard model.

LEGAL POSITIONING: The rendered text always appends LEGAL_DISCLAIMER_HE —
a hardcoded constant that is never generated, modified, or omitted by AI.

Formal Hebrew register: full sentences, passive voice where appropriate,
no colloquialisms, standard Israeli clinical writing style.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import TYPE_CHECKING, Optional

from loguru import logger

from app.ai.models import FlowType
from app.ai.router import ModelRouter

if TYPE_CHECKING:
    from app.ai.provider import AIProvider
    from app.core.agent import TherapyAgent


# ── Legal disclaimer (hardcoded — never AI-generated) ────────────────────────

LEGAL_DISCLAIMER_HE = (
    "מסמך זה נוצר בסיוע מערכת AI ועבר עריכה על ידי המטפל. "
    "האחריות המקצועית על תוכן המסמך חלה על המטפל המורשה בלבד. "
    "המסמך אינו מהווה חוות דעת משפטית או רפואית."
)


# ── Enums & dataclasses ───────────────────────────────────────────────────────

class RecordType(str, Enum):
    INTAKE_SUMMARY = "intake_summary"              # סיכום קבלה
    PROGRESS_NOTE = "progress_note"                # רשומה שוטפת
    TERMINATION_SUMMARY = "termination_summary"    # סיכום סיום טיפול
    REFERRAL_LETTER = "referral_letter"            # מכתב הפניה
    SUPERVISOR_NOTE = "supervisor_note"            # דיווח לממונה


@dataclass
class FormalRecordInput:
    """All context needed to generate a formal clinical record."""
    client_id: int
    therapist_id: int
    record_type: RecordType
    session_ids: list[int]             # which sessions were selected (for reference)
    approved_summaries: list[dict]     # approved_by_therapist=True only
    therapist_profile: dict            # name, license_type, license_number, modality, etc.
    additional_context: Optional[str] = None   # free text from therapist
    therapist_signature: Optional[str] = None  # Phase 6: inject_into_prompt() string


@dataclass
class FormalRecordResult:
    """Output of the FormalRecordPipeline.run() call."""
    record_json: dict
    rendered_text: str                 # includes LEGAL_DISCLAIMER_HE suffix
    record_type: RecordType
    model_used: str
    tokens_used: int


# ── Schema ────────────────────────────────────────────────────────────────────

FORMAL_RECORD_JSON_SCHEMA: dict = {
    "record_type": "str — one of: intake_summary, progress_note, termination_summary, referral_letter, supervisor_note",
    "client_info": {
        "age_range": "str or null — approximate age range (do not include exact DOB)",
        "referral_source": "str or null — who referred the client",
        "presenting_problem": "str — brief statement of initial presenting concern",
    },
    "treatment_summary": {
        "session_count": 0,  # REPLACE with int
        "date_range": "str — e.g. 'ינואר 2025 – מרץ 2026'",
        "modality_used": "str — primary therapeutic modality",
        "primary_diagnoses_or_themes": ["str — clinical theme or working diagnosis"],
        "goals_addressed": ["str — treatment goal that was worked on"],
        "interventions_used": ["str — named therapeutic intervention"],
    },
    "clinical_status": {
        "current_functioning": "str — brief description of current adaptive functioning",
        "risk_assessment": "str — current risk level and any safety considerations",
        "progress_rating": "str — one of: significant | moderate | minimal | none | regression",
    },
    "recommendations": ["str — specific clinical recommendation"],
    "legal_disclaimer": "",  # LEAVE EMPTY — filled by hardcoded constant post-generation
    "therapist_signature_block": {
        "name": "str — therapist full name",
        "license_type": "str — e.g. 'פסיכולוג קליני מורשה', 'עובד סוציאלי קליני'",
        "license_number": "str — license number (from therapist profile)",
        "date": "str — today's date (YYYY-MM-DD)",
    },
    "sessions_analyzed": 0,   # REPLACE with int
    "confidence": 0.85,        # REPLACE with float 0.0–1.0
}

_SCHEMA_STR = json.dumps(FORMAL_RECORD_JSON_SCHEMA, ensure_ascii=False, indent=2)


# ── Record-type specific instructions ─────────────────────────────────────────

_RECORD_TYPE_INSTRUCTIONS: dict[RecordType, str] = {
    RecordType.INTAKE_SUMMARY: (
        "This is an INTAKE SUMMARY (סיכום קבלה). "
        "Draw from the first 1–3 approved sessions only. "
        "Focus on: presenting problem, relevant background (family/social if noted), "
        "initial goals, and your first clinical impressions. "
        "Omit later-session progress — this captures the initial picture only."
    ),
    RecordType.PROGRESS_NOTE: (
        "This is a PROGRESS NOTE (רשומה שוטפת). "
        "Use a SOAP-like structure adapted for Israeli clinical standards: "
        "ס (דיווח סובייקטיבי) — client's self-report; "
        "ו (התרשמות קלינית) — objective clinical observations; "
        "ה (הערכה) — clinical assessment; "
        "ת (תכנית) — plan for continuation. "
        "Keep it concise and clinically precise."
    ),
    RecordType.TERMINATION_SUMMARY: (
        "This is a TERMINATION SUMMARY (סיכום סיום טיפול). "
        "Draw from ALL approved sessions. "
        "Cover the full treatment arc: initial goals → interventions → progress → "
        "current status → post-treatment recommendations. "
        "Include any unresolved concerns and suggested follow-up."
    ),
    RecordType.REFERRAL_LETTER: (
        "This is a REFERRAL LETTER (מכתב הפניה). "
        "Use formal letter structure. Begin with a salutation if recipient is specified. "
        "State the reason for referral clearly. "
        "Include the therapist's license number in the signature block — this is mandatory. "
        "Keep it concise (one page equivalent)."
    ),
    RecordType.SUPERVISOR_NOTE: (
        "This is a SUPERVISOR NOTE (דיווח לממונה). "
        "Be brief and clinically focused. "
        "Explicitly flag: any risk or safety concerns, ethical considerations, "
        "areas requiring supervision guidance, and your current clinical formulation. "
        "Do not include routine session content — only what requires supervisory attention."
    ),
}


# ── Prompt builders ───────────────────────────────────────────────────────────

def _build_extraction_system_prompt(inp: FormalRecordInput) -> str:
    record_instruction = _RECORD_TYPE_INSTRUCTIONS.get(inp.record_type, "")
    lines = [
        "You are a clinical documentation assistant specializing in Israeli professional standards.",
        "Your ONLY job is to extract structured clinical data from approved session summaries and return it as JSON.",
        "Return ONLY valid JSON — no prose, no markdown fences, no explanation.",
        "",
        f"Record type context: {record_instruction}",
        "",
        "IMPORTANT: Do not fabricate clinical information. Extract only what is documented in the summaries.",
        "Leave legal_disclaimer as empty string — it will be filled with a hardcoded text after generation.",
    ]
    return "\n".join(lines)


def _build_extraction_user_prompt(inp: FormalRecordInput) -> str:
    today = str(date.today())
    parts = [
        f"Record type: {inp.record_type.value}",
        f"Sessions to draw from: {len(inp.approved_summaries)} approved summary(ies)",
        f"Date of record: {today}",
        "",
    ]

    if inp.therapist_profile:
        parts.append("Therapist profile (for signature block):")
        parts.append(json.dumps(inp.therapist_profile, ensure_ascii=False, indent=2))
        parts.append("")

    if inp.additional_context:
        parts.append(f"Additional context from therapist:\n{inp.additional_context}")
        parts.append("")

    parts.append("--- Approved session summaries (oldest → newest) ---")
    for i, s in enumerate(inp.approved_summaries, 1):
        date_str = str(s.get("session_date", ""))
        num = s.get("session_number", i)
        text = s.get("full_summary", "")[:3000]
        parts.append(f"\n[Session #{num} — {date_str}]\n{text}")
    parts.append("--- End of summaries ---")

    parts.append("")
    parts.append(
        f"Fill the JSON schema below. Set sessions_analyzed={len(inp.approved_summaries)}. "
        f"Set today's date in therapist_signature_block.date='{today}'. "
        "Set confidence to your confidence level (0.0–1.0). "
        "Leave legal_disclaimer as empty string."
    )
    parts.append(f"\nJSON schema:\n{_SCHEMA_STR}")
    return "\n".join(parts)


_FORMAL_HEBREW_RENDERING_RULE = """\
FORMAL HEBREW WRITING STANDARDS (mandatory):
- Write in formal, professional Hebrew (עברית מקצועית רשמית)
- Use full, complete sentences — no bullet lists unless the record type calls for it
- Passive voice where appropriate (standard Israeli clinical writing): "נמצא", "הוערך", "דווח"
- No colloquialisms, no informal expressions
- Standard clinical terminology in Hebrew — do not mix Hebrew and English unless citing a named intervention
- Address the reader formally (גוף שלישי or appropriate clinical register)
"""


def _build_render_system_prompt(inp: FormalRecordInput) -> str:
    record_instruction = _RECORD_TYPE_INSTRUCTIONS.get(inp.record_type, "")
    return "\n".join([
        "You are a senior clinical documentation specialist preparing an official record for a patient's file.",
        "This document may be submitted to a supervisor, insurer, or included in a formal case file.",
        "",
        _FORMAL_HEBREW_RENDERING_RULE,
        "",
        f"Record type: {record_instruction}",
        "",
        "CRITICAL: Do NOT include any disclaimer text — it will be appended separately.",
        "End the document with the therapist's signature block.",
    ])


def _build_render_user_prompt(inp: FormalRecordInput, record_json: dict) -> str:
    return (
        "The structured clinical data has been extracted. "
        "Render it as a formal clinical document in the required Hebrew register.\n\n"
        f"Structured record data:\n{json.dumps(record_json, ensure_ascii=False, indent=2)}\n\n"
        "Write the complete formal record now. Do not include any disclaimer — it will be appended."
    )


# ── JSON parser ───────────────────────────────────────────────────────────────

def _parse_record_json(raw: str, record_type: RecordType) -> dict:
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
        logger.warning("FormalRecordPipeline._extract: non-JSON response, using empty scaffold")

    return {
        "record_type": record_type.value,
        "client_info": {"age_range": None, "referral_source": None, "presenting_problem": ""},
        "treatment_summary": {
            "session_count": 0,
            "date_range": "",
            "modality_used": "",
            "primary_diagnoses_or_themes": [],
            "goals_addressed": [],
            "interventions_used": [],
        },
        "clinical_status": {
            "current_functioning": "",
            "risk_assessment": "",
            "progress_rating": "none",
        },
        "recommendations": [],
        "legal_disclaimer": "",
        "therapist_signature_block": {
            "name": "",
            "license_type": "",
            "license_number": "",
            "date": str(date.today()),
        },
        "sessions_analyzed": 0,
        "confidence": 0.0,
    }


# ── Zero-summary fallback ─────────────────────────────────────────────────────

_ZERO_APPROVED_HEBREW = (
    "לא קיימים סיכומים מאושרים עבור לקוח זה. "
    "לא ניתן להפיק רשומה רשמית ללא לפחות סיכום אחד מאושר."
)


# ── FormalRecordPipeline ──────────────────────────────────────────────────────

class FormalRecordPipeline:
    """
    Two-call LLM pipeline for Israeli formal clinical records.

    Both calls use FlowType.FORMAL_RECORD → AI_DEEP_MODEL unconditionally.
    High-stakes documentation: never downgraded to fast or standard.

    After run(), legal disclaimer is appended to rendered_text by the pipeline
    (not by the caller) to guarantee it is always present.

    Call 1 (extraction): approved summaries → record_json
    Call 2 (rendering) : record_json → formal Hebrew prose (+ disclaimer suffix)
    """

    def __init__(self, provider: "AIProvider") -> None:
        self.provider = provider
        self._router = ModelRouter()
        self._last_extraction_result = None
        self._last_render_result = None

    async def run(self, inp: FormalRecordInput) -> FormalRecordResult:
        """
        Execute both calls and return a FormalRecordResult.
        Returns graceful Hebrew fallback when zero approved summaries provided.
        """
        if not inp.approved_summaries:
            return FormalRecordResult(
                record_json={},
                rendered_text=_ZERO_APPROVED_HEBREW,
                record_type=inp.record_type,
                model_used="none",
                tokens_used=0,
            )

        record_json = await self._extract(inp)
        rendered_body = await self._render(inp, record_json)

        # Hardcoded disclaimer appended by the pipeline — never AI-generated
        rendered_text = f"{rendered_body.rstrip()}\n\n---\n{LEGAL_DISCLAIMER_HE}"

        render_res = self._last_render_result
        extract_res = self._last_extraction_result
        total_tokens = 0
        if extract_res:
            total_tokens += (extract_res.prompt_tokens or 0) + (extract_res.completion_tokens or 0)
        if render_res:
            total_tokens += (render_res.prompt_tokens or 0) + (render_res.completion_tokens or 0)

        return FormalRecordResult(
            record_json=record_json,
            rendered_text=rendered_text,
            record_type=inp.record_type,
            model_used=render_res.model_used if render_res else "unknown",
            tokens_used=total_tokens,
        )

    async def _extract(self, inp: FormalRecordInput) -> dict:
        """Call 1: extract record_json from approved summaries (deep model)."""
        system_msg = _build_extraction_system_prompt(inp)
        user_msg = _build_extraction_user_prompt(inp)

        model_id, route_reason = self._router.resolve(FlowType.FORMAL_RECORD)
        result = await self.provider.generate(
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg},
            ],
            model=model_id,
            flow_type=FlowType.FORMAL_RECORD,
            route_reason=route_reason,
        )
        self._last_extraction_result = result
        return _parse_record_json(result.content, inp.record_type)

    async def _render(self, inp: FormalRecordInput, record_json: dict) -> str:
        """Call 2: render record_json into formal Hebrew prose (deep model)."""
        system_msg = _build_render_system_prompt(inp)
        # Prepend therapist signature style guidance if active (Phase 6)
        if inp.therapist_signature:
            system_msg = inp.therapist_signature + "\n\n" + system_msg
        user_msg = _build_render_user_prompt(inp, record_json)

        model_id, route_reason = self._router.resolve(FlowType.FORMAL_RECORD)
        result = await self.provider.generate(
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg},
            ],
            model=model_id,
            flow_type=FlowType.FORMAL_RECORD,
            route_reason=route_reason,
        )
        self._last_render_result = result
        return result.content
