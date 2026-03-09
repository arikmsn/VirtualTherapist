"""
Pre-Session Prep 2.0 — two-call pipeline (Phase 4).

Architecture:
  Call 1 (extraction): approved summaries → prep_json (structured JSON)
  Call 2 (rendering) : therapist_signature + prep_json → natural Hebrew prose

Mode routing:
  CONCISE      → AI_FAST_MODEL   (3 fields only, ~400 tokens)
  DEEP         → AI_STANDARD_MODEL, escalates to deep if >8 sessions
  BY_MODALITY  → AI_STANDARD_MODEL (focus on modality_checklist)
  GAP_ANALYSIS → AI_STANDARD_MODEL (focus on gaps/threads/regressions)

SOURCE OF TRUTH: Only approved_summaries (approved_by_therapist=True) are
ever passed in. This module never queries the DB — callers enforce the filter.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Optional

from loguru import logger

from app.ai.models import FlowType
from app.ai.router import ModelRouter
from app.core.config import settings

if TYPE_CHECKING:
    from app.ai.provider import AIProvider
    from app.core.agent import TherapyAgent


# ── Enums & dataclasses ───────────────────────────────────────────────────────

class PrepMode(str, Enum):
    CONCISE = "concise"
    DEEP = "deep"
    BY_MODALITY = "by_modality"
    GAP_ANALYSIS = "gap_analysis"


@dataclass
class PrepInput:
    """All context needed to generate a pre-session prep brief."""
    client_id: int
    session_id: int
    therapist_id: int
    mode: PrepMode
    modality: str                         # modality pack name (e.g. "cbt")
    approved_summaries: list[dict]        # approved_by_therapist=True only, oldest→newest
    modality_prompt_module: Optional[str] = None   # raw prompt_module from ModalityPack
    therapist_signature: Optional[dict] = None      # injected in rendering only (Phase 6)


@dataclass
class PrepResult:
    """Output of the PrepPipeline.run() call."""
    prep_json: dict
    rendered_text: str
    completeness_score: float
    completeness_data: dict
    model_used: str
    tokens_used: int


# ── Schema ────────────────────────────────────────────────────────────────────

PREP_JSON_SCHEMA: dict = {
    "client_snapshot": {
        "primary_themes": ["str — recurring theme across sessions"],
        "active_goals": ["str — current treatment goal"],
        "coping_strengths": ["str — demonstrated strength or resource"],
        "persistent_challenges": ["str — ongoing difficulty"],
    },
    "last_session_summary": {
        "key_points": ["str — main point from the most recent session"],
        "homework_given": "str or null — task assigned at last session",
        "homework_status": "str or null — status if known (e.g. 'not yet reviewed')",
        "open_threads": ["str — unresolved issue or question from prior session"],
    },
    "upcoming_session_focus": {
        "suggested_agenda": ["str — recommended agenda item for upcoming session"],
        "questions_to_explore": ["str — therapeutic question worth raising"],
        "modality_checklist": ["str — modality-specific element to cover (CBT, DBT, etc.)"],
        "risk_flags": ["str — safety or risk concern to check"],
    },
    "longitudinal_patterns": {
        "progress_narrative": "str — brief narrative of overall progress arc",
        "regression_signals": ["str — sign of backsliding or worsening"],
        "pattern_since_session_n": "int or null — session number where pattern first emerged",
    },
    "gaps": {
        "missing_information": ["str — clinically important info not yet captured"],
        "untouched_areas": ["str — topic area never explored in summaries"],
        "assessment_due": ["str — assessment or measure that should be administered"],
    },
    "mode_used": "str — one of: concise, deep, by_modality, gap_analysis",
    "sessions_analyzed": 0,  # REPLACE with int: number of approved summaries used
    "confidence": 0.85,      # REPLACE with float 0.0–1.0: confidence in extraction quality
}

_SCHEMA_STR = json.dumps(PREP_JSON_SCHEMA, ensure_ascii=False, indent=2)


# ── Field masks per mode ──────────────────────────────────────────────────────

# Maps each mode to the top-level schema keys it should populate.
# Extraction prompt instructs the model to fill ONLY these fields; others are
# left at their zero/null defaults.
_MODE_FIELDS: dict[PrepMode, list[str]] = {
    PrepMode.CONCISE: [
        "last_session_summary.key_points",
        "upcoming_session_focus.suggested_agenda",
        "upcoming_session_focus.risk_flags",
    ],
    PrepMode.DEEP: [
        "client_snapshot",
        "last_session_summary",
        "upcoming_session_focus",
        "longitudinal_patterns",
    ],
    PrepMode.BY_MODALITY: [
        "client_snapshot",
        "last_session_summary",
        "upcoming_session_focus",      # focus on modality_checklist
        "longitudinal_patterns",
    ],
    PrepMode.GAP_ANALYSIS: [
        "gaps",
        "last_session_summary.open_threads",
        "longitudinal_patterns.regression_signals",
    ],
}

_MODE_TOKEN_GUIDANCE: dict[PrepMode, str] = {
    PrepMode.CONCISE: "Keep it brief: aim for 5–7 concise Hebrew bullets (~400 tokens total).",
    PrepMode.DEEP: "Provide rich clinical depth across all sections (~900 tokens total).",
    PrepMode.BY_MODALITY: "Emphasise modality_checklist items from the active framework (~700 tokens total).",
    PrepMode.GAP_ANALYSIS: "Focus exclusively on what is missing, untouched, or regressing (~500 tokens total).",
}

# Hebrew output-length guidance appended to each mode's render user prompt.
# Moves the "stay focused" constraint to the output side rather than hard-slicing the input.
_MODE_LENGTH_GUIDANCE_HE: dict[PrepMode, str] = {
    PrepMode.CONCISE: "סכם באופן תמציתי, עד כ‑1,500 תווים לכל היותר. אל תחרוג מאורך זה.",
    PrepMode.DEEP: "כתוב הכנה מעמיקה ומפורטת, עד כ‑4,000 תווים לכל היותר.",
    PrepMode.BY_MODALITY: "התמקד בגישה הטיפולית הרלוונטית, עד כ‑3,000 תווים לכל היותר.",
    PrepMode.GAP_ANALYSIS: "פרט את הפערים והרגרסיות בלבד, עד כ‑2,000 תווים לכל היותר.",
}


# ── Prompt builders ───────────────────────────────────────────────────────────

def _build_extraction_system_prompt(inp: PrepInput) -> str:
    lines = [
        "You are a clinical data extraction assistant preparing a pre-session brief.",
        "Your ONLY job is to extract structured prep data from approved session summaries and return it as JSON.",
        "Return ONLY valid JSON — no prose, no markdown fences, no explanation.",
    ]
    if inp.modality_prompt_module:
        lines.append("")
        lines.append("## Clinical framework for this therapist:")
        lines.append(inp.modality_prompt_module.strip())
    return "\n".join(lines)


_CBT_EXTRACTION_ADDON = """\
## CBT-specific extraction rules (active — therapist uses CBT):
- upcoming_session_focus.modality_checklist must include at least 3 CBT-specific items, e.g.:
    • בדיקת מטלת בית קוגניטיבית (שאלון מחשבות, יומן רגשות)
    • זיהוי עיוותים קוגניטיביים בולטים מהסשן האחרון
    • תכנון ניסוי התנהגותי לשבוע הקרוב
    • עדכון קונספטואליזציה קוגניטיבית
- longitudinal_patterns.regression_signals: flag any return of previously challenged automatic thoughts
- last_session_summary.open_threads: include unresolved automatic thoughts or untested behavioral experiments
"""

_CBT_RENDER_ADDON = """\
## CBT framing (active):
- Section headers should reference CBT concepts naturally (e.g., "מטלת בית קוגניטיבית", "עיוות קוגניטיבי", "ניסוי התנהגותי")
- Modality checklist items must use CBT terminology — not generic phrases
- Highlight any pattern of cognitive distortions across sessions
"""


def _build_extraction_user_prompt(inp: PrepInput) -> str:
    fields_to_fill = _MODE_FIELDS.get(inp.mode, list(_MODE_FIELDS[PrepMode.DEEP]))
    token_guidance = _MODE_TOKEN_GUIDANCE.get(inp.mode, "")

    parts = [
        f"Prep mode: {inp.mode.value}",
        f"Modality: {inp.modality}",
        f"Sessions to analyze: {len(inp.approved_summaries)} approved summary(ies), oldest first.",
        "",
        "FIELDS TO POPULATE (fill ONLY these; set everything else to null / empty list):",
    ]
    for f in fields_to_fill:
        parts.append(f"  - {f}")

    if inp.modality.lower() == "cbt":
        parts.append("")
        parts.append(_CBT_EXTRACTION_ADDON.strip())

    parts.append("")
    parts.append(token_guidance)
    parts.append("")

    # Include approved summaries — summarise format for extraction
    parts.append("--- Approved session summaries (oldest → newest) ---")
    for i, s in enumerate(inp.approved_summaries, 1):
        date_str = str(s.get("session_date", ""))
        num = s.get("session_number", i)
        text = s.get("full_summary", "")  # full text — no input truncation
        parts.append(f"\n[Session #{num} — {date_str}]\n{text}")
    parts.append("--- End of summaries ---")

    parts.append("")
    parts.append(
        f"Fill the JSON schema below. Set mode_used='{inp.mode.value}' and "
        f"sessions_analyzed={len(inp.approved_summaries)}. "
        "Set confidence to your confidence level (0.0–1.0)."
    )
    parts.append(f"\nJSON schema:\n{_SCHEMA_STR}")
    return "\n".join(parts)


def _build_render_system_prompt(inp: PrepInput) -> str:
    lines = [
        "You are preparing a pre-session brief for a therapist, in the therapist's voice.",
        "Write in natural, professional Hebrew. Be concise and clinically useful.",
        "Do NOT list fields mechanically — integrate the content into flowing prose or well-structured bullets.",
    ]
    if inp.therapist_signature:
        lines.append("")
        lines.append(str(inp.therapist_signature))
    return "\n".join(lines)


def _build_render_user_prompt(inp: PrepInput, prep_json: dict) -> str:
    token_guidance = _MODE_TOKEN_GUIDANCE.get(inp.mode, "")
    length_guidance = _MODE_LENGTH_GUIDANCE_HE.get(inp.mode, "")
    cbt_block = f"\n\n{_CBT_RENDER_ADDON.strip()}" if inp.modality.lower() == "cbt" else ""
    return (
        f"Mode: {inp.mode.value} — {token_guidance}{cbt_block}\n\n"
        "The structured prep data has been extracted. Render it as a ready-to-use "
        "pre-session brief that the therapist can scan in under 60 seconds.\n\n"
        f"Structured prep data:\n{json.dumps(prep_json, ensure_ascii=False, indent=2)}\n\n"
        f"{length_guidance}\n\n"
        "Write the pre-session brief now."
    )


# ── JSON parser ───────────────────────────────────────────────────────────────

def _parse_prep_json(raw: str, mode: PrepMode) -> dict:
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
        logger.warning("PrepPipeline._extract: non-JSON response, using empty scaffold")

    return {
        "client_snapshot": {"primary_themes": [], "active_goals": [], "coping_strengths": [], "persistent_challenges": []},
        "last_session_summary": {"key_points": [], "homework_given": None, "homework_status": None, "open_threads": []},
        "upcoming_session_focus": {"suggested_agenda": [], "questions_to_explore": [], "modality_checklist": [], "risk_flags": []},
        "longitudinal_patterns": {"progress_narrative": "", "regression_signals": [], "pattern_since_session_n": None},
        "gaps": {"missing_information": [], "untouched_areas": [], "assessment_due": []},
        "mode_used": mode.value,
        "sessions_analyzed": 0,
        "confidence": 0.0,
    }


# ── PrepPipeline ──────────────────────────────────────────────────────────────

_ZERO_APPROVED_HEBREW = (
    "לא קיימים סיכומים מאושרים עבור מטופל זה. "
    "הכנה מקדימה אינה זמינה — אנא אשר לפחות סיכום אחד לפני יצירת ההכנה."
)


class PrepPipeline:
    """
    Two-call LLM pipeline for pre-session prep briefs.

    Call 1 — extraction (stores GenerationResult in _last_extraction_result):
        approved summaries → prep_json dict via JSON-focused system prompt

    Call 2 — rendering (stores GenerationResult in _last_render_result):
        prep_json + therapist signature → natural Hebrew prose

    Usage:
        pipeline = PrepPipeline(agent)
        result = await pipeline.run(prep_input)

    After run(), callers use _last_extraction_result and _last_render_result
    to write separate ai_generation_log rows.
    """

    # Escalation threshold for DEEP mode (session count → standard → deep tier)
    _DEEP_ESCALATION_THRESHOLD = 8

    def __init__(self, agent: "TherapyAgent") -> None:
        self.agent = agent
        self._router = ModelRouter()
        self._last_extraction_result = None   # GenerationResult from Call 1
        self._last_render_result = None        # GenerationResult from Call 2

    async def run(self, inp: PrepInput) -> PrepResult:
        """
        Execute both calls and return a PrepResult.
        Returns a graceful Hebrew fallback (no LLM call) when zero approved
        summaries are provided — never fabricates.
        """
        if not inp.approved_summaries:
            return PrepResult(
                prep_json={},
                rendered_text=_ZERO_APPROVED_HEBREW,
                completeness_score=0.0,
                completeness_data={},
                model_used="none",
                tokens_used=0,
            )

        prep_json = await self._extract(inp)
        rendered = await self._render(inp, prep_json)

        render_result = self._last_render_result
        extract_result = self._last_extraction_result
        total_tokens = 0
        if extract_result:
            total_tokens += (extract_result.prompt_tokens or 0) + (extract_result.completion_tokens or 0)
        if render_result:
            total_tokens += (render_result.prompt_tokens or 0) + (render_result.completion_tokens or 0)

        return PrepResult(
            prep_json=prep_json,
            rendered_text=rendered,
            completeness_score=0.0,   # filled by session_service after CompletenessChecker
            completeness_data={},     # filled by session_service after CompletenessChecker
            model_used=render_result.model_used if render_result else "unknown",
            tokens_used=total_tokens,
        )

    def _resolve_model(self, inp: PrepInput) -> tuple[str, str]:
        """Return (model_id, route_reason) based on mode and session count."""
        session_count = len(inp.approved_summaries)
        if inp.mode == PrepMode.CONCISE:
            model_id = settings.AI_FAST_MODEL
            return model_id, f"mode:concise,tier:fast"
        if inp.mode == PrepMode.DEEP and session_count > self._DEEP_ESCALATION_THRESHOLD:
            model_id = settings.AI_DEEP_MODEL
            return model_id, f"mode:deep,tier:deep,escalated:session_count>{self._DEEP_ESCALATION_THRESHOLD}"
        # Standard tier for DEEP (≤8 sessions), BY_MODALITY, GAP_ANALYSIS
        model_id = settings.AI_STANDARD_MODEL
        return model_id, f"mode:{inp.mode.value},tier:standard"

    async def _extract(self, inp: PrepInput) -> dict:
        """Call 1: extract prep_json from approved summaries."""
        system_msg = _build_extraction_system_prompt(inp)
        user_msg = _build_extraction_user_prompt(inp)

        model_id, route_reason = self._resolve_model(inp)
        result = await self.agent.provider.generate(
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg},
            ],
            model=model_id,
            flow_type=FlowType.SESSION_PREP,
            route_reason=route_reason,
        )
        self._last_extraction_result = result
        return _parse_prep_json(result.content, inp.mode)

    async def _render(self, inp: PrepInput, prep_json: dict) -> str:
        """Call 2: render prep_json into Hebrew prose with optional therapist signature."""
        system_msg = _build_render_system_prompt(inp)
        user_msg = _build_render_user_prompt(inp, prep_json)

        model_id, route_reason = self._resolve_model(inp)
        result = await self.agent.provider.generate(
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg},
            ],
            model=model_id,
            flow_type=FlowType.SESSION_PREP,
            route_reason=route_reason,
        )
        self._last_render_result = result
        self.agent._last_result = result
        return result.content

    async def extract_only(self, inp: PrepInput) -> dict:
        """Run extraction call only (Call 1). Used by streaming endpoints."""
        return await self._extract(inp)

    async def render_stream(self, inp: PrepInput, prep_json: dict):
        """
        Stream the render call (Call 2) token by token.
        Yields raw text chunks. Used by the /prep/stream SSE endpoint.
        """
        system_msg = _build_render_system_prompt(inp)
        user_msg = _build_render_user_prompt(inp, prep_json)
        model_id, route_reason = self._resolve_model(inp)

        async for chunk in self.agent.provider.generate_stream(
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg},
            ],
            model=model_id,
            flow_type=FlowType.SESSION_PREP,
            route_reason=route_reason,
        ):
            yield chunk
