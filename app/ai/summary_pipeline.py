"""
Session Summary 2.0 — two-call pipeline (Phase 3).

Architecture:
  Call 1 (extraction): therapist notes → clinical_json (structured JSON)
  Call 2 (rendering) : clinical_json  → natural Hebrew prose (full_summary)
  Call 3 (completeness): handled separately by CompletenessChecker in session_service

Both calls use FlowType.SESSION_SUMMARY → routed to AI_STANDARD_MODEL.

The intermediate clinical_json is stored in session_summaries.clinical_json for
audit, future analysis, and Phase 6 signature learning.  The rendered prose is
what therapists see and edit (stored in session_summaries.full_summary).
"""

from __future__ import annotations

import difflib
import json
from dataclasses import dataclass, field
from datetime import date
from typing import TYPE_CHECKING, Optional

from loguru import logger

from app.ai.models import FlowType
from app.ai.router import ModelRouter

if TYPE_CHECKING:
    from app.core.agent import TherapyAgent
    from app.models.modality import ModalityPack
    from app.models.signature import TherapistSignatureProfile


# ── SummaryInput ──────────────────────────────────────────────────────────────

@dataclass
class SummaryInput:
    """All context needed to generate a session summary."""

    raw_content: str                            # therapist notes or ASR transcript
    client_name: str
    session_number: int
    session_date: date
    last_approved_summary: Optional[str]        # full_summary from most recent APPROVED row
    open_tasks: list[str]                       # unresolved homework from prior sessions
    modality_pack: Optional["ModalityPack"]
    therapist_signature: Optional[str] = None  # Phase 6: inject_into_prompt() string
    flow_type: FlowType = FlowType.SESSION_SUMMARY


# ── CLINICAL_JSON_SCHEMA ──────────────────────────────────────────────────────

# Used as a template in the extraction prompt so the model knows exactly what to fill.
CLINICAL_JSON_SCHEMA: dict = {
    "session_focus": "str — main focus / presenting concern of this session",
    "key_themes": ["str — recurring theme or topic"],
    "interventions_used": ["str — name of specific intervention used"],
    "client_response": "str — how the client responded to interventions and discussion",
    "homework_reviewed": {
        "was_reviewed": "bool — was previous homework discussed?",
        "completed": "bool or null — did the client complete it?",
        "barriers": "str or null — what prevented completion?",
    },
    "automatic_thoughts": [
        "str — quote or paraphrase of automatic thought (CBT; empty list for other modalities)"
    ],
    "cognitive_distortions": [
        "str — name the distortion explicitly (CBT; empty list for other modalities)"
    ],
    "new_homework": "str or null — specific between-session task assigned",
    "mood_observed": "str or null — observed emotional state or mood rating",
    "risk_assessment": {
        "risk_present": "bool — is there a safety concern?",
        "notes": "str or null — describe the concern if risk_present is true",
    },
    "next_session_focus": "str or null — planned focus for the next session",
    "longitudinal_note": "str or null — connection to the previous session or treatment arc",
    "confidence": 0.85,  # REPLACE with float 0.0–1.0: your confidence in the extraction
}

_SCHEMA_STR = json.dumps(CLINICAL_JSON_SCHEMA, ensure_ascii=False, indent=2)


# ── Extraction prompt builders ────────────────────────────────────────────────

_CBT_EXTRACTION_SYSTEM_ADDON = """\
## CBT extraction rules (active — therapist uses CBT):
- automatic_thoughts: extract EVERY automatic thought mentioned (quoted or paraphrased); do NOT leave empty
- cognitive_distortions: name each distortion explicitly (e.g., "קטסטרופיזציה", "חשיבה שחור-לבן", "אישיות יתר")
- interventions_used: must include CBT-specific techniques (e.g., "ניסוי התנהגותי", "בחינת עדויות", "שאלות סוקרטיות")
- homework_reviewed: always document whether previous CBT homework was reviewed and the client's completion status
"""


def _build_extraction_system_prompt(modality_pack: Optional["ModalityPack"]) -> str:
    lines = ["You are a clinical data extraction assistant."]
    lines.append(
        "Your ONLY job is to extract structured clinical data from session notes and return it as JSON."
    )
    lines.append("Return ONLY valid JSON — no prose, no markdown fences, no explanation.")
    if modality_pack and modality_pack.prompt_module:
        lines.append("")
        lines.append("## Clinical framework for this therapist:")
        lines.append(modality_pack.prompt_module.strip())
    if modality_pack and modality_pack.name == "cbt":
        lines.append("")
        lines.append(_CBT_EXTRACTION_SYSTEM_ADDON.strip())
    return "\n".join(lines)


def _build_extraction_user_prompt(inp: SummaryInput) -> str:
    parts = [
        f"Patient: {inp.client_name}",
        f"Session #{inp.session_number}, {inp.session_date}",
    ]
    if inp.open_tasks:
        tasks_str = "\n".join(f"- {t}" for t in inp.open_tasks)
        parts.append(f"\nOpen tasks from previous sessions (pending homework):\n{tasks_str}")
    if inp.last_approved_summary:
        parts.append(
            f"\nLast approved summary (for longitudinal context):\n{inp.last_approved_summary}"
        )
    else:
        parts.append("\nLast approved summary: None available — this appears to be the first session.")

    parts.append(f"\n--- Session notes ---\n{inp.raw_content}\n--- End of notes ---")
    parts.append(f"\nFill the JSON schema below based ONLY on the notes above. Do not invent information.")
    parts.append(f"Set 'confidence' to your confidence level (0.0–1.0) in the extraction quality.")
    parts.append(f"\nJSON schema:\n{_SCHEMA_STR}")
    return "\n".join(parts)


# ── Render prompt builder ─────────────────────────────────────────────────────

_CBT_RENDER_SECTION = """\
## מבנה סיכום בסגנון CBT (פעיל):
- פתח עם מיקוד הסשן ומצב רוח שנצפה
- סקור מטלת הבית הקוגניטיבית מהפגישה הקודמת (הושלמה? מחסומים?)
- תאר מחשבות אוטומטיות ועיוותים קוגניטיביים שזוהו — ציטוט ישיר אם אפשר
- תאר התערבויות קוגניטיביות-התנהגותיות שנעשו
- סיים עם מטלת הבית החדשה ומיקוד הפגישה הבאה
- אם חסרים נתוני CBT (מחשבות אוטומטיות / עיוותים), סמן: ⚠️ חסר
"""


def _build_render_prompt(inp: SummaryInput, clinical_json: dict) -> str:
    is_cbt = inp.modality_pack is not None and inp.modality_pack.name == "cbt"
    cbt_block = f"\n{_CBT_RENDER_SECTION}" if is_cbt else ""
    return (
        "The structured clinical data for this session has been extracted. "
        "Render it as a natural, cohesive session summary in the therapist's voice.\n\n"
        f"Guidelines:\n"
        "- Do NOT list fields mechanically. Integrate the content naturally.\n"
        "- Write as if the therapist is documenting their own session.\n"
        "- If the modality requires specific elements that are absent, "
        f"flag them at the end as: ⚠️ חסר: [element]{cbt_block}\n\n"
        f"Structured session data:\n{json.dumps(clinical_json, ensure_ascii=False, indent=2)}\n\n"
        "Write the session summary now."
    )


# ── JSON parser ───────────────────────────────────────────────────────────────

def _parse_clinical_json(raw: str) -> dict:
    """
    Parse the extraction call's response into a dict.
    Falls back to a minimal dict on any failure — never raises.
    """
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
        logger.warning("SummaryPipeline._extract: non-JSON response, using empty scaffold")

    return {
        "session_focus": "",
        "key_themes": [],
        "interventions_used": [],
        "client_response": "",
        "homework_reviewed": {"was_reviewed": False, "completed": None, "barriers": None},
        "automatic_thoughts": [],
        "cognitive_distortions": [],
        "new_homework": None,
        "mood_observed": None,
        "risk_assessment": {"risk_present": False, "notes": None},
        "next_session_focus": None,
        "longitudinal_note": None,
        "confidence": 0.0,
    }


# ── Edit distance ─────────────────────────────────────────────────────────────

def compute_edit_distance(text_a: str, text_b: str) -> int:
    """
    Approximate character-level edit distance between two strings.

    Uses difflib.SequenceMatcher (stdlib, no extra dependencies).
    Formula: total_chars * (1 - similarity_ratio) ≈ number of edited characters.

    Low value (<50): therapist accepted with minimal edits.
    High value: significant rewrite — valuable signal for signature learning.
    """
    if not text_a and not text_b:
        return 0
    if not text_a:
        return len(text_b)
    if not text_b:
        return len(text_a)

    sm = difflib.SequenceMatcher(None, text_a, text_b, autojunk=False)
    total = len(text_a) + len(text_b)
    # matching_blocks sum gives M (matching chars); edit distance ≈ T - 2*M
    matching = sum(block.size for block in sm.get_matching_blocks())
    return max(0, total - 2 * matching)


# ── SummaryPipeline ────────────────────────────────────────────────────────────

class SummaryPipeline:
    """
    Two-call LLM pipeline that replaces the single-call generate_session_summary.

    Call 1 — extraction (stores GenerationResult in _last_extraction_result):
        notes → clinical_json dict via JSON-focused system prompt

    Call 2 — rendering (stores GenerationResult in _last_render_result):
        clinical_json → natural Hebrew prose via the agent's full system prompt
        (which already contains modality framing from Phase 2 assemble_system_prompt)

    Usage:
        pipeline = SummaryPipeline(agent)
        clinical_json, rendered_text = await pipeline.run(summary_input)

    After run(), callers use _last_extraction_result and _last_render_result
    to write separate ai_generation_log rows.
    """

    def __init__(self, agent: "TherapyAgent") -> None:
        self.agent = agent
        self._router = ModelRouter()
        self._last_extraction_result = None   # GenerationResult from Call 1
        self._last_render_result = None        # GenerationResult from Call 2

    async def run(self, summary_input: SummaryInput) -> tuple[dict, str]:
        """
        Execute both calls and return (clinical_json_dict, rendered_summary_text).
        The rendered text is what therapists see; clinical_json is the intermediate artifact.
        """
        clinical_json = await self._extract(summary_input)
        rendered = await self._render(summary_input, clinical_json)
        return clinical_json, rendered

    async def _extract(self, inp: SummaryInput) -> dict:
        """Call 1: extract clinical_json from session notes."""
        system_msg = _build_extraction_system_prompt(inp.modality_pack)
        user_msg = _build_extraction_user_prompt(inp)

        model_id, route_reason = self._router.resolve(inp.flow_type)
        result = await self.agent.provider.generate(
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg},
            ],
            model=model_id,
            flow_type=inp.flow_type,
            route_reason=route_reason,
        )
        self._last_extraction_result = result
        return _parse_clinical_json(result.content)

    async def _render(self, inp: SummaryInput, clinical_json: dict) -> str:
        """Call 2: render clinical_json into Hebrew prose using the agent's system prompt."""
        render_prompt = _build_render_prompt(inp, clinical_json)

        # Prepend therapist signature style guidance if active (Phase 6)
        system_prompt = self.agent.system_prompt
        if inp.therapist_signature:
            system_prompt = inp.therapist_signature + "\n\n" + system_prompt

        model_id, route_reason = self._router.resolve(inp.flow_type)
        result = await self.agent.provider.generate(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": render_prompt},
            ],
            model=model_id,
            flow_type=inp.flow_type,
            route_reason=route_reason,
        )
        self._last_render_result = result
        # Keep agent._last_result pointing to the render result (the visible output)
        self.agent._last_result = result
        return result.content
