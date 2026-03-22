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
from typing import TYPE_CHECKING, Any, Dict, Optional

from loguru import logger

from app.ai.models import FlowType
from app.ai.router import ModelRouter
from app.core.config import settings
from app.core.ai_context import format_protocol_block

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
    ai_context: Optional[dict] = None              # built by build_ai_context_for_patient()


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
        "OUTPUT RULES (strictly enforced):",
        "  1. Respond with ONLY valid JSON — no explanations, no markdown, no prose.",
        "  2. Start your response with { and end it with }.",
        "  3. Use ONLY the field names defined in the schema below. Do not add extra fields.",
        "  4. If a field has no data, use null or [] — never write explanatory text inside JSON values.",
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
        "Set confidence to your confidence level (0.0–1.0). "
        "Keep all string values concise (≤ 100 chars each). "
        "Start your response immediately with { and end it with }."
    )
    parts.append(f"\nJSON schema:\n{_SCHEMA_STR}")

    # Minimal Hebrew example — structure reference only, not clinical content
    _example = {
        "client_snapshot": {
            "primary_themes": ["חרדה חברתית", "דפוסי הימנעות"],
            "active_goals": ["הפחתת הימנעות"],
            "coping_strengths": ["מודעות עצמית"],
            "persistent_challenges": ["קושי בחשיפה"],
        },
        "last_session_summary": {
            "key_points": ["עבדנו על מחשבות אוטומטיות"],
            "homework_given": "יומן מחשבות יומי",
            "homework_status": "לא נבדק",
            "open_threads": ["חרדה בעבודה"],
        },
        "upcoming_session_focus": {
            "suggested_agenda": ["בדיקת מטלה", "ניסוי חשיפה"],
            "questions_to_explore": ["מה הפעיל את החרדה השבוע?"],
            "modality_checklist": [],
            "risk_flags": [],
        },
        "longitudinal_patterns": {
            "progress_narrative": "שיפור הדרגתי בוויסות רגשי",
            "regression_signals": [],
            "pattern_since_session_n": None,
        },
        "gaps": {"missing_information": [], "untouched_areas": [], "assessment_due": []},
        "mode_used": inp.mode.value,
        "sessions_analyzed": len(inp.approved_summaries),
        "confidence": 0.8,
    }
    parts.append(
        "\nMinimal valid example (structure only — use real data from summaries above):\n"
        + json.dumps(_example, ensure_ascii=False)
    )
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
    protocol_block = format_protocol_block(inp.ai_context)
    protocol_guidance = ""
    if protocol_block:
        protocol_guidance = (
            "\nWhen preparing the pre-session brief:\n"
            "- If the patient has an active protocol in the JSON, align the focus, "
            "suggested questions, and homework ideas with that protocol and its stage.\n"
            "- If the JSON includes 'completed_sessions' and 'typical_sessions', infer the treatment phase "
            "(early ≈ first third, middle ≈ middle third, late ≈ final third) and adjust the tone accordingly: "
            "early sessions favor psychoeducation and rapport-building, "
            "middle sessions favor active skill application and experiments, "
            "late sessions favor consolidation and relapse prevention.\n"
            "- Never state the numeric stage count in the Hebrew output; only adapt the clinical language and emphasis.\n"
            "- If no protocol is set, keep the brief general but still respect the "
            "therapist's profession and approaches.\n"
            "- Do not invent protocol names or stages that are not present in the JSON.\n"
        )
    return (
        f"Mode: {inp.mode.value} — {token_guidance}{cbt_block}\n\n"
        "The structured prep data has been extracted. Render it as a ready-to-use "
        "pre-session brief that the therapist can scan in under 60 seconds.\n\n"
        f"Structured prep data:\n{json.dumps(prep_json, ensure_ascii=False, indent=2)}\n\n"
        f"{length_guidance}\n"
        f"{protocol_guidance}"
        f"{protocol_block}\n\n"
        "Write the pre-session brief now."
    )


# ── Envelope-based prompt builders (spec §5.1, §5.2) ─────────────────────────
# These replace the PrepInput-based builders for the v3 pipeline path.

def _build_extraction_system_prompt_v2(envelope: Dict[str, Any]) -> str:
    """
    Implements spec §5.1 — extraction system prompt derived from LLMContextEnvelope.

    Injects modality_prompt_module from envelope['extra']['modality_prompt_module'].
    """
    lines = [
        "You are a clinical data extraction assistant preparing a pre-session brief.",
        "Your ONLY job is to map the provided patient clinical state into the prep JSON schema.",
        "OUTPUT RULES (strictly enforced):",
        "  1. Respond with ONLY valid JSON — no explanations, no markdown, no prose.",
        "  2. Start your response with { and end it with }.",
        "  3. Use ONLY the field names defined in the schema below. Do not add extra fields.",
        "  4. If a field has no data, use null or [] — never write explanatory text inside JSON values.",
    ]
    modality_prompt_module = envelope.get("extra", {}).get("modality_prompt_module")
    if modality_prompt_module:
        lines.append("")
        lines.append("## Clinical framework for this therapist:")
        lines.append(modality_prompt_module.strip())
    return "\n".join(lines)


def _build_extraction_user_prompt_v2(envelope: Dict[str, Any]) -> str:
    """
    Implements spec §5.1 — extraction user prompt built from LLMContextEnvelope.

    Populates the prep schema from envelope.patient_state instead of raw summary text.
    """
    mode_str = envelope.get("request_mode") or "concise"
    try:
        mode = PrepMode(mode_str)
    except ValueError:
        mode = PrepMode.CONCISE

    patient_state = envelope["patient_state"]
    sessions_analyzed: int = patient_state["metadata"]["sessions_analyzed"]
    modality: str = envelope.get("extra", {}).get("modality", "generic_integrative")
    fields_to_fill = _MODE_FIELDS.get(mode, list(_MODE_FIELDS[PrepMode.DEEP]))
    token_guidance = _MODE_TOKEN_GUIDANCE.get(mode, "")

    parts = [
        f"Prep mode: {mode.value}",
        f"Modality: {modality}",
        f"Sessions analyzed: {sessions_analyzed} approved session(s).",
        "",
        "FIELDS TO POPULATE (fill ONLY these; set everything else to null / empty list):",
    ]
    for f in fields_to_fill:
        parts.append(f"  - {f}")

    if modality.lower() == "cbt":
        parts.append("")
        parts.append(_CBT_EXTRACTION_ADDON.strip())

    parts.append("")
    parts.append(token_guidance)
    parts.append("")

    # Patient clinical state — structured input derived from approved summaries
    parts.append("--- Patient clinical state (derived from approved session summaries) ---")
    parts.append(json.dumps(patient_state, ensure_ascii=False, indent=2))
    parts.append("--- End of patient state ---")

    parts.append("")
    parts.append(
        f"Fill the JSON schema below. Set mode_used='{mode.value}' and "
        f"sessions_analyzed={sessions_analyzed}. "
        "Set confidence to your confidence level (0.0–1.0). "
        "Keep all string values concise (≤ 100 chars each). "
        "Start your response immediately with { and end it with }."
    )
    parts.append(f"\nJSON schema:\n{_SCHEMA_STR}")

    # Minimal Hebrew example — structure reference only
    _example = {
        "client_snapshot": {
            "primary_themes": ["חרדה חברתית"],
            "active_goals": ["הפחתת הימנעות"],
            "coping_strengths": ["מודעות עצמית"],
            "persistent_challenges": ["קושי בחשיפה"],
        },
        "last_session_summary": {
            "key_points": ["עבדנו על מחשבות אוטומטיות"],
            "homework_given": "יומן מחשבות",
            "homework_status": "לא נבדק",
            "open_threads": ["חרדה בעבודה"],
        },
        "upcoming_session_focus": {
            "suggested_agenda": ["בדיקת מטלה"],
            "questions_to_explore": ["מה הפעיל את החרדה?"],
            "modality_checklist": [],
            "risk_flags": [],
        },
        "longitudinal_patterns": {
            "progress_narrative": "שיפור הדרגתי",
            "regression_signals": [],
            "pattern_since_session_n": None,
        },
        "gaps": {"missing_information": [], "untouched_areas": [], "assessment_due": []},
        "mode_used": mode.value,
        "sessions_analyzed": sessions_analyzed,
        "confidence": 0.8,
    }
    parts.append(
        "\nMinimal valid example (structure only — use real data from patient state above):\n"
        + json.dumps(_example, ensure_ascii=False)
    )
    return "\n".join(parts)


def _build_render_system_prompt_v2(envelope: Dict[str, Any]) -> str:
    """
    Implements spec §5.2 — render system prompt from LLMContextEnvelope.

    Injects therapist style and enforces language + no-question-at-end rules.
    """
    style = envelope["therapist_style"]
    constraints = envelope["ai_constraints"]
    sessions_analyzed: int = envelope["patient_state"]["metadata"]["sessions_analyzed"]

    lines = [
        "You are preparing a pre-session brief for a therapist, in the therapist's voice.",
        f"Write in natural, professional {'Hebrew' if constraints['language'] == 'he' else constraints['language'].upper()}.",
        "Be concise and clinically useful.",
        "Do NOT list fields mechanically — integrate the content into flowing prose or well-structured bullets.",
        "Do NOT end the brief with a question or question mark.",
    ]

    # Prohibitions / custom rules (spec §5.2 — constraints)
    if constraints["prohibitions"]:
        lines.append("")
        lines.append("RULES — you must NEVER:")
        for p in constraints["prohibitions"]:
            lines.append(f"  - {p}")

    if constraints["custom_rules"]:
        lines.append("")
        lines.append("Additional rules:")
        for r in constraints["custom_rules"]:
            lines.append(f"  - {r}")

    # Sessions-analyzed behavioral rules (spec §5.2)
    lines.append("")
    if sessions_analyzed == 0:
        lines.append(
            "NOTE: No approved session summaries exist yet for this patient. "
            "You MAY state this clearly in Hebrew (e.g. 'אין עדיין סיכומים מאושרים'). "
            "Base the brief ONLY on protocol context if available. Do NOT invent session content."
        )
    else:
        lines.append(
            f"CRITICAL — {sessions_analyzed} approved session summaries are available. "
            "These are real clinical records. You MUST produce a clinically grounded prep brief. "
            "The user prompt contains both structured prep_json AND the full patient_state "
            "(longitudinal_state, last_session_state, etc.) — draw from ALL of it.\n"
            "\n"
            "ABSOLUTELY FORBIDDEN — never write any of the following, under any circumstances:\n"
            "  • 'אין נתונים' or any claim that data is missing\n"
            "  • 'לא ניתן לגבש תמונה קלינית' or 'cannot generate clinical picture'\n"
            "  • 'מבוסס על פרוטוקול בלבד' or 'protocol only'\n"
            "  • 'סיכומי הפגישות שהועברו אינם מכילים מידע קליני' or similar\n"
            "  • 'לא ידוע', 'N/A', 'no data'\n"
            "  • Any sentence saying the summaries lack clinical information\n"
            "\n"
            "REQUIRED — the brief MUST include at least 2–3 concrete clinical details "
            "(themes, events, homework, risk, progress) drawn from the data below. "
            "If a specific JSON field is empty, draw from other non-empty fields or from "
            "patient_state — there is always something to write when sessions exist. "
            "Skip empty sections silently rather than explaining their absence."
        )

    # Therapist style injection (matches existing inject_into_prompt() output format)
    sig_count = envelope.get("extra", {}).get("approved_sample_count", 0)
    min_required = envelope.get("extra", {}).get("min_samples_required", 5)
    if sig_count >= min_required and style.get("style_summary"):
        lines.append("")
        lines.append(f"סגנון הכתיבה המועדף של המטפל (למד מ-{sig_count} עריכות מאושרות):")
        lines.append(style["style_summary"])
        if style.get("style_examples"):
            ex = '", "'.join(style["style_examples"][:3])
            lines.append(f'דוגמאות לסגנון: "{ex}"')
        hints = []
        if style.get("preferred_sentence_length"):
            hints.append(f"משפטים {style['preferred_sentence_length']}")
        if style.get("preferred_voice"):
            hints.append(f"גוף {'פעיל' if style['preferred_voice'] == 'active' else 'סביל' if style['preferred_voice'] == 'passive' else 'מעורב'}")
        if style.get("uses_clinical_jargon") is not None:
            hints.append("עם ז'רגון קליני" if style["uses_clinical_jargon"] else "ללא ז'רגון קליני")
        if hints:
            lines.append(f"הנחיות: {', '.join(hints)}.")

    return "\n".join(lines)


def _build_render_user_prompt_v2(envelope: Dict[str, Any], prep_json: Dict[str, Any]) -> str:
    """
    Implements spec §5.2 — render user prompt from LLMContextEnvelope.
    """
    mode_str = envelope.get("request_mode") or "concise"
    try:
        mode = PrepMode(mode_str)
    except ValueError:
        mode = PrepMode.CONCISE

    modality: str = envelope.get("extra", {}).get("modality", "generic_integrative")
    token_guidance = _MODE_TOKEN_GUIDANCE.get(mode, "")
    length_guidance = _MODE_LENGTH_GUIDANCE_HE.get(mode, "")
    cbt_block = f"\n\n{_CBT_RENDER_ADDON.strip()}" if modality.lower() == "cbt" else ""

    # Protocol block comes from envelope's ai_context (stored in extra by the caller)
    ai_context = envelope.get("extra", {}).get("ai_context")
    protocol_block = format_protocol_block(ai_context) if ai_context else ""
    protocol_guidance = ""
    if protocol_block:
        protocol_guidance = (
            "\nWhen preparing the pre-session brief:\n"
            "- If the patient has an active protocol in the JSON, align the focus, "
            "suggested questions, and homework ideas with that protocol and its stage.\n"
            "- Infer the treatment phase (early/middle/late) from completed_sessions / typical_sessions "
            "and adapt the tone accordingly.\n"
            "- Never state the numeric stage count in the Hebrew output.\n"
            "- If no protocol is set, keep the brief general but respect the therapist's approaches.\n"
        )

    # Include patient_state as fallback clinical context when prep_json is sparse
    patient_state = envelope.get("patient_state", {})
    patient_state_block = ""
    if patient_state:
        patient_state_block = (
            "Additional clinical context (longitudinal patient state — use this if "
            "prep_json fields are empty):\n"
            f"{json.dumps(patient_state, ensure_ascii=False, indent=2)}\n\n"
        )

    return (
        f"Mode: {mode.value} — {token_guidance}{cbt_block}\n\n"
        "The structured prep data has been extracted. Render it as a ready-to-use "
        "pre-session brief that the therapist can scan in under 60 seconds.\n\n"
        f"Structured prep data:\n{json.dumps(prep_json, ensure_ascii=False, indent=2)}\n\n"
        f"{patient_state_block}"
        f"{length_guidance}\n"
        f"{protocol_guidance}"
        f"{protocol_block}\n\n"
        "Write the pre-session brief now."
    )


# ── No-data guard ────────────────────────────────────────────────────────────

_NO_DATA_PHRASES = [
    "אין נתונים",
    "לא ניתן לגבש תמונה קלינית מבוססת נתונים",
    "מבוסס על פרוטוקול בלבד",
    "אין מידע קליני",
    "סיכומי הפגישות שהועברו אינם מכילים",
    "protocol only",
    "no data",
]


def _contains_no_data_phrase(text: str) -> bool:
    """Return True if the rendered text contains a forbidden 'no data' phrase."""
    lower = text.lower()
    return any(p.lower() in lower for p in _NO_DATA_PHRASES)


# ── JSON parser ───────────────────────────────────────────────────────────────

def _empty_prep_scaffold(mode: PrepMode, sessions_analyzed: int = 0) -> dict:
    """Return an empty prep scaffold. sessions_analyzed=0 signals a failed extraction."""
    return {
        "client_snapshot": {
            "primary_themes": [], "active_goals": [],
            "coping_strengths": [], "persistent_challenges": [],
        },
        "last_session_summary": {
            "key_points": [], "homework_given": None,
            "homework_status": None, "open_threads": [],
        },
        "upcoming_session_focus": {
            "suggested_agenda": [], "questions_to_explore": [],
            "modality_checklist": [], "risk_flags": [],
        },
        "longitudinal_patterns": {
            "progress_narrative": "", "regression_signals": [],
            "pattern_since_session_n": None,
        },
        "gaps": {"missing_information": [], "untouched_areas": [], "assessment_due": []},
        "mode_used": mode.value,
        "sessions_analyzed": sessions_analyzed,
        "confidence": 0.0,
    }


def _parse_prep_json(raw: "str | dict", mode: PrepMode, sessions_analyzed: int = 0) -> dict:
    """
    Parse extraction response into a dict.

    Accepts str or dict (dict pass-through for callers that pre-parsed).
    Tries in order:
      1. Direct json.loads if string.
      2. Regex fence strip (```json ... ```) then json.loads.
      3. Brace-matching: find first { and its matching } by depth counting.
    Falls back to empty scaffold only when all three fail.
    """
    import re

    # Already a dict — pass through
    if isinstance(raw, dict):
        return raw

    cleaned = raw.strip()

    # Attempt 1: direct parse
    try:
        data = json.loads(cleaned)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass

    # Attempt 2: strip markdown fences
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, re.DOTALL)
    if fence_match:
        try:
            data = json.loads(fence_match.group(1))
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass

    # Attempt 3: brace-matching salvage — find first { and walk to its closing }
    start = cleaned.find("{")
    if start != -1:
        depth = 0
        in_string = False
        escape_next = False
        for i, ch in enumerate(cleaned[start:], start):
            if escape_next:
                escape_next = False
                continue
            if ch == "\\" and in_string:
                escape_next = True
                continue
            if ch == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    candidate = cleaned[start:i + 1]
                    try:
                        data = json.loads(candidate)
                        if isinstance(data, dict):
                            logger.warning(
                                "PrepPipeline._extract: salvaged JSON via brace-matching "
                                "(prefix=%d chars, suffix=%d chars)",
                                start,
                                len(cleaned) - i - 1,
                            )
                            return data
                    except json.JSONDecodeError:
                        break

    # All attempts failed — log debug info and return empty scaffold
    logger.warning(
        "PrepPipeline._extract: non-JSON response, using empty scaffold "
        "(first 300: %r … last 100: %r)",
        cleaned[:300],
        cleaned[-100:],
    )
    return _empty_prep_scaffold(mode, sessions_analyzed=0)


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
            # max_tokens for extraction: production traces show fully-populated DEEP JSON
            # is ~1200–1800 tokens. 3200 gives a 2× safety buffer without being wasteful.
            # (Default 2000 caused truncation: production log showed out=2000 exactly.)
            max_tokens=3200,
        )
        self._last_extraction_result = result
        return _parse_prep_json(result.content, inp.mode, sessions_analyzed=len(inp.approved_summaries))

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

    async def extract_only(self, inp: "PrepInput | dict") -> dict:
        """
        Run extraction Call 1.

        Accepts either a legacy PrepInput (backward compat) or a LLMContextEnvelope dict
        (spec §5.1).  Used by streaming endpoints and run_with_envelope().
        """
        if isinstance(inp, dict):
            return await self._extract_v2(inp)
        return await self._extract(inp)

    async def render_stream(self, inp: "PrepInput | dict", prep_json: dict):
        """
        Stream render Call 2, token by token.

        Accepts either a legacy PrepInput or a LLMContextEnvelope dict (spec §5.2).
        Yields raw text chunks.  Used by the /prep/stream SSE endpoint.
        """
        if isinstance(inp, dict):
            async for chunk in self._render_stream_v2(inp, prep_json):
                yield chunk
            return

        # Legacy PrepInput path
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

    # ── Envelope-aware internal methods (spec §5.1, §5.2) ────────────────────

    def _resolve_model_v2(self, envelope: dict) -> tuple:
        """Return (model_id, route_reason) from envelope request_mode + sessions_analyzed."""
        mode_str = envelope.get("request_mode") or "concise"
        try:
            mode = PrepMode(mode_str)
        except ValueError:
            mode = PrepMode.CONCISE
        session_count: int = envelope["patient_state"]["metadata"]["sessions_analyzed"]
        if mode == PrepMode.CONCISE:
            return settings.AI_FAST_MODEL, "mode:concise,tier:fast"
        if mode == PrepMode.DEEP and session_count > self._DEEP_ESCALATION_THRESHOLD:
            return settings.AI_DEEP_MODEL, f"mode:deep,tier:deep,escalated:count>{self._DEEP_ESCALATION_THRESHOLD}"
        return settings.AI_STANDARD_MODEL, f"mode:{mode.value},tier:standard"

    async def _extract_v2(self, envelope: dict) -> dict:
        """Envelope-based extraction call (spec §5.1)."""
        system_msg = _build_extraction_system_prompt_v2(envelope)
        user_msg = _build_extraction_user_prompt_v2(envelope)
        model_id, route_reason = self._resolve_model_v2(envelope)

        result = await self.agent.provider.generate(
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg},
            ],
            model=model_id,
            flow_type=FlowType.SESSION_PREP,
            route_reason=route_reason,
            # max_tokens for extraction: production traces show fully-populated DEEP JSON
            # is ~1200–1800 tokens. 3200 gives a 2× safety buffer without being wasteful.
            # (Default 2000 caused truncation: production log showed out=2000 exactly.)
            max_tokens=3200,
        )
        self._last_extraction_result = result
        sessions_analyzed: int = envelope["patient_state"]["metadata"]["sessions_analyzed"]
        mode_str = envelope.get("request_mode") or "concise"
        try:
            mode = PrepMode(mode_str)
        except ValueError:
            mode = PrepMode.CONCISE
        return _parse_prep_json(result.content, mode, sessions_analyzed=sessions_analyzed)

    async def _render_v2(self, envelope: dict, prep_json: dict) -> str:
        """Envelope-based render call (spec §5.2)."""
        system_msg = _build_render_system_prompt_v2(envelope)
        user_msg = _build_render_user_prompt_v2(envelope, prep_json)
        model_id, route_reason = self._resolve_model_v2(envelope)

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
        text = result.content

        # Code-level guard: if no-data phrases appear despite sessions existing, retry once
        sessions_analyzed: int = envelope["patient_state"]["metadata"]["sessions_analyzed"]
        if sessions_analyzed > 0 and _contains_no_data_phrase(text):
            logger.warning(
                "[prep_guard] no-data phrase detected with sessions_analyzed=%d; retrying render",
                sessions_analyzed,
            )
            retry_system = system_msg + (
                "\n\nFINAL WARNING: Your previous response contained a forbidden 'no data' phrase. "
                "This is incorrect — the patient has real clinical history. "
                "Rewrite the brief now using ONLY concrete details from the prep data and patient state. "
                "Do NOT mention missing information."
            )
            retry_result = await self.agent.provider.generate(
                messages=[
                    {"role": "system", "content": retry_system},
                    {"role": "user", "content": user_msg},
                ],
                model=model_id,
                flow_type=FlowType.SESSION_PREP,
                route_reason=route_reason + ",retry:no_data_guard",
            )
            self._last_render_result = retry_result
            self.agent._last_result = retry_result
            text = retry_result.content

        return text

    async def _render_stream_v2(self, envelope: dict, prep_json: dict):
        """Streaming render call from envelope (spec §5.2)."""
        system_msg = _build_render_system_prompt_v2(envelope)
        user_msg = _build_render_user_prompt_v2(envelope, prep_json)
        model_id, route_reason = self._resolve_model_v2(envelope)

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

    async def render_only(self, envelope: dict, prep_json: dict) -> "PrepResult":
        """
        Run the render call only — skip extraction.

        Used by the render_only cache tier: the existing session.prep_json (previous
        extraction) is rendered with a fresh envelope (current therapist style /
        patient state). One LLM call → ~10–15 s response time.
        """
        sessions_analyzed: int = envelope["patient_state"]["metadata"]["sessions_analyzed"]
        if sessions_analyzed == 0:
            return PrepResult(
                prep_json=prep_json,
                rendered_text=_ZERO_APPROVED_HEBREW,
                completeness_score=0.0,
                completeness_data={},
                model_used="none",
                tokens_used=0,
            )

        rendered = await self._render_v2(envelope, prep_json)
        render_result = self._last_render_result
        tokens = 0
        if render_result:
            tokens = (render_result.prompt_tokens or 0) + (render_result.completion_tokens or 0)

        return PrepResult(
            prep_json=prep_json,
            rendered_text=rendered,
            completeness_score=0.0,
            completeness_data={},
            model_used=render_result.model_used if render_result else "unknown",
            tokens_used=tokens,
        )

    async def run_with_envelope(self, envelope: dict) -> "PrepResult":
        """
        Execute extraction + render using LLMContextEnvelope (spec §5.1, §5.2).

        Returns graceful Hebrew fallback when sessions_analyzed == 0 (spec §5.2).
        """
        sessions_analyzed: int = envelope["patient_state"]["metadata"]["sessions_analyzed"]
        if sessions_analyzed == 0:
            return PrepResult(
                prep_json={},
                rendered_text=_ZERO_APPROVED_HEBREW,
                completeness_score=0.0,
                completeness_data={},
                model_used="none",
                tokens_used=0,
            )

        prep_json = await self._extract_v2(envelope)
        rendered = await self._render_v2(envelope, prep_json)

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
            completeness_score=0.0,   # filled by caller after CompletenessChecker
            completeness_data={},
            model_used=render_result.model_used if render_result else "unknown",
            tokens_used=total_tokens,
        )
