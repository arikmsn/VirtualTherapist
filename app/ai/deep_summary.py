"""
Deep Summary + Therapist Reference Vault — Phase 8.

Architecture:
  DeepSummaryPipeline:
    < 5 sessions : 2 calls  — extraction + rendering
    5–10 sessions: 3 calls  — extraction + synthesis + rendering
    > 10 sessions: N+2 calls — N chunk extractions + synthesis + rendering

  All calls use FlowType.DEEP_SUMMARY → AI_DEEP_MODEL.

  VaultExtractor:
    Single standard-model call post-generation to extract clinical insights.
    Deduplicated by content. Capped at 15 entries per client.

  VaultRetriever:
    DB query with tag-matching. Injects relevant context into rendering call.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Optional

from loguru import logger

from app.ai.models import FlowType
from app.ai.router import ModelRouter
from app.core.ai_context import format_protocol_block

if TYPE_CHECKING:
    from app.ai.provider import AIProvider

# ── Constants ─────────────────────────────────────────────────────────────────

_CHUNK_SIZE = 10                 # summaries per extraction chunk
_SHORT_HISTORY_THRESHOLD = 5     # below this: skip chunking, 2-call pipeline
_MAX_VAULT_ENTRIES = 15          # per client cap


# ── Enums ─────────────────────────────────────────────────────────────────────

class VaultEntryType(str, Enum):
    CLINICAL_PATTERN = "clinical_pattern"         # recurring behavioral/cognitive pattern
    THERAPEUTIC_BREAKTHROUGH = "breakthrough"      # session with significant shift
    RISK_HISTORY = "risk_history"                 # documented risk events
    TREATMENT_RESPONSE = "treatment_response"     # what worked / what didn't
    DIAGNOSTIC_NOTE = "diagnostic_note"           # clinical hypotheses


# ── Dataclasses ───────────────────────────────────────────────────────────────

@dataclass
class DeepSummaryInput:
    """All context needed to generate a deep longitudinal summary."""
    client_id: int
    therapist_id: int
    modality: str
    approved_summaries: list[dict]          # ALL approved summaries, oldest → newest
    treatment_plan: Optional[dict] = None   # active plan_json if exists
    therapist_signature: Optional[str] = None
    ai_context: Optional[dict] = None      # built by build_ai_context_for_patient()


@dataclass
class DeepSummaryResult:
    """Output of DeepSummaryPipeline.run()."""
    summary_json: dict
    rendered_text: str
    vault_entries_created: int      # entries extracted and stored
    model_used: str
    tokens_used: int


@dataclass
class VaultEntry:
    """A single extracted clinical insight ready for storage."""
    entry_type: str
    content: str
    tags: list[str]
    confidence: float
    source_session_ids: list[int]


# ── Deep Summary JSON schema ──────────────────────────────────────────────────

DEEP_SUMMARY_JSON_SCHEMA: dict = {
    "arc_narrative": "",
    "presenting_problem_evolution": "",
    "treatment_phases": [
        {
            "phase_label": "",
            "session_range": "",
            "primary_focus": "",
            "key_developments": [],
        }
    ],
    "goals_outcome": [
        {
            "goal": "",
            "outcome": "achieved | partial | not_achieved | ongoing",
            "evidence": "",
        }
    ],
    "clinical_patterns_identified": [],
    "turning_points": [],
    "what_worked": [],
    "what_didnt_work": [],
    "current_status": "",
    "recommendations_going_forward": [],
    "sessions_covered": 0,
    "confidence": 0.0,
}

_SCHEMA_STR = json.dumps(DEEP_SUMMARY_JSON_SCHEMA, ensure_ascii=False, indent=2)

# ── Zero-summary fallback ─────────────────────────────────────────────────────

_ZERO_APPROVED_HEBREW = (
    "לא קיימים סיכומים מאושרים עבור לקוח זה. "
    "לא ניתן להפיק סיכום עמוק ללא לפחות סיכום אחד מאושר."
)

# ── Vault extraction prompt ───────────────────────────────────────────────────

_VAULT_EXTRACTION_SYSTEM = """\
Extract discrete clinical insights from a treatment summary.
Each insight must be self-contained and reusable for future clinical decisions.
Respond ONLY with a valid JSON array. No prose, no markdown fences.

Valid entry_type values:
  "clinical_pattern"    — recurring behavioral or cognitive patterns
  "breakthrough"        — sessions with significant therapeutic shift
  "treatment_response"  — what interventions worked or didn't for this client
  "diagnostic_note"     — clinical hypotheses about underlying dynamics

For each entry produce:
{
  "entry_type": "",
  "content": "",           // Hebrew, 1–3 sentences, self-contained
  "tags": [],              // 2–5 descriptive Hebrew tags
  "confidence": 0.0,
  "source_session_ids": [] // session numbers this insight is based on
}

Quality rules:
- Maximum 15 entries. Prefer quality over quantity.
- Each entry must stand alone without the full context.
- Focus on what's clinically distinctive about this specific client.
"""


# ── "No data" phrase detection ────────────────────────────────────────────────

# Substrings (lowercased) that indicate the model wrote a placeholder instead of
# real clinical content.  Used to prevent Hebrew "no data" boilerplate from
# passing the _has_extracted_content check and bypassing _render_direct().
_NO_DATA_MARKERS = [
    # Hebrew
    "לא נמסר מידע",
    "לא ניתן להעריך",
    "לא זוהו מטרות",
    "לא זוהו דפוסים",
    "לא זוהו נקודות",
    "לא זוהו שינויים",
    "חסר תוכן מספק",
    "חסר מידע",
    "המידע שהועבר לסינתזה",
    "המידע הקליני שהועבר",
    "המידע לסינתזה",
    "מידע לא מספיק",
    "אין מידע מספיק",
    "אין נתונים",
    "לא ניתן לזהות",
    # English (guard against future regressions)
    "insufficient",
    "no data",
    "no clinical",
    "not provided",
]


def _is_meaningful_string(text: str) -> bool:
    """Return True if text is real clinical content, not a 'no data' placeholder."""
    if not text or len(text) < 15:
        return False
    low = text.lower()
    return not any(marker in low for marker in _NO_DATA_MARKERS)


# ── Prompt builders ───────────────────────────────────────────────────────────

_CBT_EXTRACTION_NOTE = """\

CBT EXTRACTION FOCUS (mandatory for this case):
- clinical_patterns_identified: list recurring automatic thoughts, cognitive distortions,
  and avoidance behaviors observed across sessions (in Hebrew)
- turning_points: list sessions where a meaningful cognitive or behavioral shift occurred
- what_worked: list CBT techniques that helped (e.g., behavioral experiments, thought records,
  Socratic questioning, exposure) — extract from session notes even if not explicitly labelled
- what_didnt_work: list what the client resisted, what produced no change, or what was abandoned
- treatment_phases: label phases by the dominant CBT focus (psychoeducation / exposure /
  cognitive restructuring / relapse prevention etc.)
- goals_outcome: link each goal to a cognitive or behavioral target
Do NOT leave any of these fields empty if the session notes contain any clinical narrative."""


def _build_chunk_extraction_system(modality: str = "") -> str:
    cbt_block = _CBT_EXTRACTION_NOTE if modality.lower() == "cbt" else ""
    return "\n".join([
        "You are a clinical documentation assistant performing longitudinal analysis.",
        "Extract structured data from the provided session summaries.",
        "Return ONLY valid JSON — no prose, no markdown fences.",
        "",
        "LANGUAGE REQUIREMENT: All string values in the JSON must be written in Hebrew (עברית).",
        "If source notes are in Hebrew, extract and summarize in Hebrew.",
        "CRITICAL: If a field has no relevant content, use an empty string '' or empty list [] "
        "— do NOT write any placeholder text in any language "
        "(no 'insufficient data', no 'לא נמסר מידע', no 'לא זוהו', etc.).",
        "",
        "Focus on: treatment_phases, goals_outcome, clinical_patterns_identified, "
        "turning_points, what_worked, what_didnt_work.",
        "",
        "Use the JSON schema provided. Omit arc_narrative and current_status "
        "(those are added in synthesis). Set sessions_covered to the number of sessions in this chunk.",
    ]) + cbt_block


def _build_chunk_extraction_user(summaries: list[dict], chunk_index: int, total_chunks: int) -> str:
    parts = [
        f"Chunk {chunk_index + 1} of {total_chunks} — {len(summaries)} session(s):",
        "",
        "--- Session summaries ---",
    ]
    for s in summaries:
        date_str = str(s.get("session_date", ""))
        num = s.get("session_number", "?")
        text = s.get("full_summary") or ""  # full text — no input truncation
        parts.append(f"\n[Session #{num} — {date_str}]\n{text}")
    parts.append("--- End ---")
    parts.append(f"\nFill partial JSON schema:\n{_SCHEMA_STR}")
    return "\n".join(parts)


def _build_synthesis_system() -> str:
    return "\n".join([
        "You are a senior clinical analyst synthesizing partial treatment summaries.",
        "Merge the provided chunk analyses into one cohesive full treatment summary.",
        "Return ONLY valid JSON matching the schema. No prose, no markdown fences.",
        "",
        "LANGUAGE REQUIREMENT: All string values in the JSON must be written in Hebrew (עברית).",
        "CRITICAL: If a field has no relevant content, use an empty string '' or empty list [] "
        "— do NOT write any placeholder text in any language "
        "(not 'insufficient data', not 'לא נמסר מידע', not 'לא זוהו', not 'חסר מידע', etc.).",
        "",
        "Add arc_narrative, presenting_problem_evolution, current_status, "
        "and recommendations_going_forward based on the full picture.",
    ])


def _build_synthesis_user(
    merged_chunks: list[dict],
    inp: DeepSummaryInput,
) -> str:
    plan_section = ""
    if inp.treatment_plan:
        plan_section = (
            f"\nActive treatment plan:\n"
            f"{json.dumps(inp.treatment_plan, ensure_ascii=False, indent=2)}\n"
        )

    cbt_hint = (
        "\nCBT synthesis note: track the evolution of automatic thoughts and "
        "cognitive distortions across chunks; highlight cognitive shifts as turning_points.\n"
        if inp.modality.lower() == "cbt" else ""
    )

    protocol_block = format_protocol_block(inp.ai_context)
    protocol_guidance = ""
    if protocol_block:
        protocol_guidance = (
            "\nUse the protocol context JSON to understand:\n"
            "- which structured protocols the therapist is following with this patient,\n"
            "- how many sessions a typical protocol might include,\n"
            "- what core techniques are expected.\n"
            "When synthesizing, try to describe the treatment arc also in relation to these protocols "
            "(e.g., early psychoeducation, mid-treatment behavioral experiments, late relapse prevention), "
            "but only when the chunk analyses support such an interpretation.\n"
        )

    chunk_text = json.dumps(merged_chunks, ensure_ascii=False, indent=2)
    return (
        f"Modality: {inp.modality}\n"
        f"Total sessions: {len(inp.approved_summaries)}\n"
        f"{plan_section}{cbt_hint}"
        f"{protocol_guidance}"
        f"{protocol_block}\n"
        f"Chunk analyses to merge:\n{chunk_text}\n\n"
        f"Synthesize into a complete summary following this schema:\n{_SCHEMA_STR}"
    )


_FORMAL_HEBREW_NARRATIVE_RULE = """\
NARRATIVE WRITING STANDARDS:
- Write a flowing Hebrew clinical narrative — not bullet points
- Formal professional register (עברית מקצועית)
- Structure with clear sections: background, treatment arc, key developments,
  outcomes, current status, recommendations
- Include the arc_narrative as the opening paragraph
"""

_CBT_DEEP_SUMMARY_ADDON = """\
## סיכום עמוק בגישת CBT (פעיל):
- תאר את האבולוציה של הדפוסים הקוגניטיביים לאורך הטיפול
- זהה עיוותים קוגניטיביים חוזרים ואת השינוי בהם לאורך הזמן
- תאר אילו ניסויים התנהגותיים בוצעו ומה היו תוצאותיהם
- הפרד בין "מה עבד" ל"מה לא עבד" בנקודת מבט קוגניטיבית-התנהגותית
- recommendations_going_forward חייב להכיל לפחות 2 המלצות CBT ספציפיות
"""


def _build_render_system(inp: DeepSummaryInput) -> str:
    cbt_block = f"\n\n{_CBT_DEEP_SUMMARY_ADDON.strip()}" if inp.modality.lower() == "cbt" else ""
    base = "\n".join([
        "You are a senior clinical documentation specialist preparing a comprehensive treatment narrative.",
        "This document covers the full arc of treatment and will be used for clinical review.",
        "",
        _FORMAL_HEBREW_NARRATIVE_RULE,
    ]) + cbt_block
    if inp.therapist_signature:
        base = inp.therapist_signature + "\n\n" + base
    return base


def _build_render_user(
    summary_json: dict,
    vault_context: Optional[str],
    inp: DeepSummaryInput,
) -> str:
    vault_section = ""
    if vault_context:
        vault_section = f"\nתובנות קליניות מהכספת:\n{vault_context}\n"

    protocol_block = format_protocol_block(inp.ai_context)
    protocol_guidance = ""
    if protocol_block:
        protocol_guidance = (
            "\nWhen writing the narrative:\n"
            "- If the patient has an active protocol, frame the treatment story in relation to that "
            "protocol's logic: where the treatment started, what phases were covered, and what remains.\n"
            "- Use 'completed_sessions' vs. 'typical_sessions' in the JSON to gauge the patient's "
            "current phase within each active protocol (early / middle / late), and let the narrative "
            "naturally reflect that arc in Hebrew — e.g., 'בשלב הנוכחי של הטיפול…' or "
            "'לקראת שלב מניעת נסיגה…'. Never write numeric session counts in the output.\n"
            "- For CBT protocols, emphasize automatic thoughts, distortions, and behavioral experiments "
            "in line with the protocol description.\n"
            "- Do not expose protocol IDs or raw JSON; just let the narrative reflect this structure "
            "naturally in Hebrew.\n"
        )

    return (
        "The structured treatment data has been extracted. "
        "Render it as a complete formal Hebrew clinical narrative.\n\n"
        f"{protocol_guidance}"
        f"{protocol_block}\n"
        f"Structured summary:\n{json.dumps(summary_json, ensure_ascii=False, indent=2)}\n"
        f"{vault_section}\n"
        "כתוב סיכום עומק ממוקד ומקיף, עד 3,000 תווים בדיוק. "
        "הקפד לסיים במשפט שלם — אל תיחתך באמצע מילה או משפט. "
        "אל תחרוג מאורך זה.\n\n"
        "Write the complete deep summary narrative in Hebrew now."
    )


# ── JSON parsers ──────────────────────────────────────────────────────────────

def _parse_summary_json(raw: str) -> dict:
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
        logger.warning("DeepSummaryPipeline: non-JSON extraction response")
    return {
        "arc_narrative": "",
        "presenting_problem_evolution": "",
        "treatment_phases": [],
        "goals_outcome": [],
        "clinical_patterns_identified": [],
        "turning_points": [],
        "what_worked": [],
        "what_didnt_work": [],
        "current_status": "",
        "recommendations_going_forward": [],
        "sessions_covered": 0,
        "confidence": 0.0,
    }


def _parse_vault_entries(raw: str) -> list[dict]:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        parts = cleaned.split("```")
        cleaned = parts[1] if len(parts) > 1 else cleaned
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
    cleaned = cleaned.strip()
    try:
        data = json.loads(cleaned)
        if isinstance(data, list):
            return data
    except json.JSONDecodeError:
        logger.warning("VaultExtractor: non-JSON response")
    return []


_RENDERED_TEXT_HARD_LIMIT = 3000   # characters; enforced after generation


def _truncate_at_sentence(text: str, limit: int = _RENDERED_TEXT_HARD_LIMIT) -> str:
    """
    Hard-limit rendered_text to `limit` characters, cutting at the last complete
    sentence boundary before the limit.  Sentence boundaries: `. `, `! `, `? `,
    `.\n`, `!\n`, `?\n`.  Falls back to the raw slice if no boundary is found.
    """
    if len(text) <= limit:
        return text
    chunk = text[:limit]
    # Search backwards for a sentence-ending punctuation followed by space or newline
    for i in range(len(chunk) - 1, max(len(chunk) - 200, 0), -1):
        if chunk[i] in ".!?" and (i + 1 >= len(chunk) or chunk[i + 1] in " \n"):
            return chunk[: i + 1].rstrip()
    # No boundary found — just hard-cut and add ellipsis
    return chunk.rstrip() + "…"


# ── DeepSummaryPipeline ───────────────────────────────────────────────────────

class DeepSummaryPipeline:
    """
    Longitudinal clinical narrative pipeline.

    < 5 sessions : 2 LLM calls (extraction + rendering)
    5–10 sessions: 3 LLM calls (extraction + synthesis + rendering)
    > 10 sessions: N+2 calls   (N chunk extractions + synthesis + rendering)

    Vault context (from VaultRetriever) is injected into the rendering call only.
    """

    def __init__(self, provider: "AIProvider") -> None:
        self.provider = provider
        self._router = ModelRouter()
        self._extraction_results: list = []
        self._synthesis_result = None
        self._render_result = None

    def total_tokens(self) -> int:
        total = 0
        for r in self._extraction_results:
            if r:
                total += (r.prompt_tokens or 0) + (r.completion_tokens or 0)
        for r in (self._synthesis_result, self._render_result):
            if r:
                total += (r.prompt_tokens or 0) + (r.completion_tokens or 0)
        return total

    async def run(
        self,
        inp: DeepSummaryInput,
        vault_context: Optional[str] = None,
    ) -> DeepSummaryResult:
        if not inp.approved_summaries:
            return DeepSummaryResult(
                summary_json={},
                rendered_text=_ZERO_APPROVED_HEBREW,
                vault_entries_created=0,
                model_used="none",
                tokens_used=0,
            )

        n = len(inp.approved_summaries)

        if n < _SHORT_HISTORY_THRESHOLD:
            # Short history: single extraction call → render
            summary_json = await self._extract_single(inp)
        else:
            # Longer history: chunk extraction(s) → synthesis → render
            chunks = [
                inp.approved_summaries[i: i + _CHUNK_SIZE]
                for i in range(0, n, _CHUNK_SIZE)
            ]
            chunk_results = []
            total_chunks = len(chunks)
            for idx, chunk in enumerate(chunks):
                chunk_json = await self._extract_chunk(chunk, idx, total_chunks, inp.modality)
                chunk_results.append(chunk_json)
            summary_json = await self._synthesize(chunk_results, inp)

        # If extraction produced no real content, fall back to a direct render.
        # _is_meaningful_string() rejects both empty strings AND Hebrew/English
        # "no data" placeholders that the model sometimes writes instead of empty strings.
        _content_fields = (
            "arc_narrative", "presenting_problem_evolution", "treatment_phases",
            "goals_outcome", "clinical_patterns_identified", "turning_points",
            "what_worked", "what_didnt_work", "current_status",
        )
        _has_extracted_content = any(
            (isinstance(summary_json.get(k), str) and _is_meaningful_string(summary_json.get(k, "")))
            or (
                isinstance(summary_json.get(k), list)
                and len(summary_json.get(k, [])) > 0
                and any(_is_meaningful_string(str(item)) for item in summary_json.get(k, []))
            )
            for k in _content_fields
        )
        if not _has_extracted_content:
            logger.warning(
                f"[deep_summary] extraction produced empty/placeholder JSON for "
                f"client={inp.client_id} modality={inp.modality!r} "
                f"(confidence={summary_json.get('confidence', 0.0)}) — "
                f"falling back to direct render from {n} session summaries"
            )
            # Direct render: skip the structured JSON layer, pass sessions directly
            rendered_text = await self._render_direct(inp, vault_context)
        else:
            rendered_text = await self._render(inp, summary_json, vault_context)

        # Hard-limit to _RENDERED_TEXT_HARD_LIMIT at a sentence boundary
        rendered_text = _truncate_at_sentence(rendered_text)

        model_used = "unknown"
        if self._render_result:
            model_used = self._render_result.model_used

        return DeepSummaryResult(
            summary_json=summary_json,
            rendered_text=rendered_text,
            vault_entries_created=0,   # caller fills this after vault extraction
            model_used=model_used,
            tokens_used=self.total_tokens(),
        )

    async def _extract_single(self, inp: DeepSummaryInput) -> dict:
        """Single extraction call for short histories (< 5 sessions)."""
        system = _build_chunk_extraction_system(inp.modality)
        user = _build_chunk_extraction_user(inp.approved_summaries, 0, 1)
        model_id, route_reason = self._router.resolve(FlowType.DEEP_SUMMARY)
        result = await self.provider.generate(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            model=model_id,
            flow_type=FlowType.DEEP_SUMMARY,
            route_reason=route_reason,
        )
        self._extraction_results.append(result)
        return _parse_summary_json(result.content)

    async def _extract_chunk(
        self,
        chunk: list[dict],
        chunk_index: int,
        total_chunks: int,
        modality: str = "",
    ) -> dict:
        """One extraction call per chunk."""
        system = _build_chunk_extraction_system(modality)
        user = _build_chunk_extraction_user(chunk, chunk_index, total_chunks)
        model_id, route_reason = self._router.resolve(FlowType.DEEP_SUMMARY)
        result = await self.provider.generate(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            model=model_id,
            flow_type=FlowType.DEEP_SUMMARY,
            route_reason=route_reason,
        )
        self._extraction_results.append(result)
        return _parse_summary_json(result.content)

    async def _synthesize(self, chunk_results: list[dict], inp: DeepSummaryInput) -> dict:
        """Merge chunk extractions into full summary_json."""
        system = _build_synthesis_system()
        user = _build_synthesis_user(chunk_results, inp)
        model_id, route_reason = self._router.resolve(FlowType.DEEP_SUMMARY)
        result = await self.provider.generate(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            model=model_id,
            flow_type=FlowType.DEEP_SUMMARY,
            route_reason=route_reason,
        )
        self._synthesis_result = result
        return _parse_summary_json(result.content)

    async def _render(
        self,
        inp: DeepSummaryInput,
        summary_json: dict,
        vault_context: Optional[str],
    ) -> str:
        """Render summary_json into formal Hebrew prose."""
        system = _build_render_system(inp)
        user = _build_render_user(summary_json, vault_context, inp)
        model_id, route_reason = self._router.resolve(FlowType.DEEP_SUMMARY)
        result = await self.provider.generate(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            model=model_id,
            flow_type=FlowType.DEEP_SUMMARY,
            route_reason=route_reason,
        )
        self._render_result = result
        return result.content

    async def _render_direct(
        self,
        inp: DeepSummaryInput,
        vault_context: Optional[str],
    ) -> str:
        """
        Fallback render: skip structured JSON extraction, render a full clinical narrative
        directly from the raw session summaries. Used when JSON extraction produces empty output.
        """
        vault_section = ""
        if vault_context:
            vault_section = f"\nתובנות קליניות מהכספת:\n{vault_context}\n"

        sessions_text = "\n".join(
            f"\n[פגישה #{s.get('session_number', i + 1)} — {s.get('session_date', '')}]\n{s.get('full_summary') or ''}"
            for i, s in enumerate(inp.approved_summaries)
        )

        if inp.modality.lower() == "cbt":
            task_instruction = (
                "כתוב סיכום עומק CBT מקיף ומפורט בעברית, עד 3,000 תווים בדיוק. "
                "חובה לכלול את כל הסעיפים הבאים על בסיס המידע הקליני שסופק — "
                "אין להשאיר סעיף ריק אם קיים מידע רלוונטי:\n"
                "1. **רקע ודפוסים קוגניטיביים**: מחשבות אוטומטיות, עיוותים קוגניטיביים חוזרים שזוהו\n"
                "2. **מהלך הטיפול ושלביו**: אבחון, פסיכוחינוך CBT, רשת מחשבות-רגשות-התנהגות\n"
                "3. **ניסויים התנהגותיים ותוצאותיהם**: מה בוצע ומה היה השינוי\n"
                "4. **מה עבד — מנקודת מבט CBT**: טכניקות שהניבו שינוי קוגניטיבי או התנהגותי\n"
                "5. **מה לא עבד**: התנגדויות, הימנעויות, מה לא הושלם\n"
                "6. **שינויים קוגניטיביים מרכזיים**: נקודות מפנה שבהן השתנתה תפיסת המטופל\n"
                "7. **מצב נוכחי**: הערכה קוגניטיבית-התנהגותית של המצב היום\n"
                "8. **המלצות CBT להמשך**: לפחות 2 המלצות ספציפיות (טכניקות, מטרות, שיעורי בית)\n"
                "הקפד לסיים במשפט שלם. אל תחרוג מאורך זה.\n\n"
                "Write the complete CBT deep summary narrative in Hebrew now."
            )
        else:
            task_instruction = (
                "כתוב סיכום עומק ממוקד ומקיף בעברית, עד 3,000 תווים בדיוק. "
                "כסה: רצף הטיפול, דפוסים קליניים, מה עבד, מה לא עבד, מצב נוכחי, המלצות להמשך. "
                "הקפד לסיים במשפט שלם — אל תיחתך באמצע מילה או משפט. "
                "אל תחרוג מאורך זה.\n\n"
                "Write the complete deep summary narrative in Hebrew now."
            )

        protocol_block = format_protocol_block(inp.ai_context)
        protocol_guidance = ""
        if protocol_block:
            protocol_guidance = (
                "\nWhen writing the narrative:\n"
                "- If the patient has an active protocol, frame the treatment story in relation to that "
                "protocol's logic: where the treatment started, what phases were covered, and what remains.\n"
                "- Do not expose protocol IDs or raw JSON; let the narrative reflect this structure "
                "naturally in Hebrew.\n"
            )

        user = (
            f"Modality: {inp.modality}\n"
            f"Total sessions: {len(inp.approved_summaries)}\n"
            f"{vault_section}\n"
            f"{protocol_guidance}"
            f"{protocol_block}\n"
            "--- Session summaries (oldest → newest) ---\n"
            f"{sessions_text}\n"
            "--- End ---\n\n"
            f"{task_instruction}"
        )

        system = _build_render_system(inp)
        model_id, route_reason = self._router.resolve(FlowType.DEEP_SUMMARY)
        result = await self.provider.generate(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            model=model_id,
            flow_type=FlowType.DEEP_SUMMARY,
            route_reason=route_reason,
        )
        self._render_result = result
        return result.content


# ── VaultExtractor ────────────────────────────────────────────────────────────

class VaultExtractor:
    """
    Extracts reusable clinical insights from a deep summary.

    Uses standard model (FlowType.VAULT_EXTRACTION).
    Never raises — best-effort only.
    """

    def __init__(self, provider: "AIProvider") -> None:
        self.provider = provider
        self._router = ModelRouter()
        self._last_result = None

    async def extract_entries(
        self,
        summary_json: dict,
        client_id: int,
        therapist_id: int,
        source_session_ids: list[int],
    ) -> list[VaultEntry]:
        """Run extraction, return list of VaultEntry objects. Never raises."""
        try:
            model_id, route_reason = self._router.resolve(FlowType.VAULT_EXTRACTION)
            user_content = (
                f"Treatment summary for client {client_id} "
                f"(sessions: {source_session_ids}):\n\n"
                f"{json.dumps(summary_json, ensure_ascii=False, indent=2)}"
            )
            result = await self.provider.generate(
                messages=[
                    {"role": "system", "content": _VAULT_EXTRACTION_SYSTEM},
                    {"role": "user", "content": user_content},
                ],
                model=model_id,
                flow_type=FlowType.VAULT_EXTRACTION,
                route_reason=route_reason,
            )
            self._last_result = result
            raw_entries = _parse_vault_entries(result.content)
        except Exception as exc:
            logger.warning(f"VaultExtractor.extract_entries failed: {exc!r}")
            return []

        entries = []
        for e in raw_entries[:_MAX_VAULT_ENTRIES]:
            try:
                entries.append(VaultEntry(
                    entry_type=str(e.get("entry_type", "clinical_pattern")),
                    content=str(e.get("content", "")),
                    tags=list(e.get("tags", [])),
                    confidence=float(e.get("confidence", 0.5)),
                    source_session_ids=list(e.get("source_session_ids", source_session_ids)),
                ))
            except Exception:
                continue
        return entries


# ── VaultRetriever ────────────────────────────────────────────────────────────

class VaultRetriever:
    """
    Retrieves relevant vault entries for a client using tag matching.

    Phase 8: simple tag-matching (no embeddings yet).
    Results sorted by confidence descending.
    """

    def __init__(self, db) -> None:
        self.db = db

    async def get_relevant_entries(
        self,
        client_id: int,
        therapist_id: int,
        query_tags: list[str],
        entry_types: Optional[list[str]] = None,
        limit: int = 5,
    ) -> list[dict]:
        """
        Return relevant vault entries by tag intersection.

        Falls back to returning all active entries for the client
        if no tag matches exist.
        """
        try:
            from app.models.reference_vault import TherapistReferenceVault

            query = (
                self.db.query(TherapistReferenceVault)
                .filter(
                    TherapistReferenceVault.therapist_id == therapist_id,
                    TherapistReferenceVault.client_id == client_id,
                    TherapistReferenceVault.is_active == True,  # noqa: E712
                )
            )
            if entry_types:
                query = query.filter(
                    TherapistReferenceVault.entry_type.in_(entry_types)
                )

            rows = query.all()
            if not rows:
                return []

            # Score by tag intersection count
            q_tags = {t.lower() for t in query_tags}
            scored = []
            for row in rows:
                row_tags = {t.lower() for t in (row.tags or [])}
                score = len(q_tags & row_tags)
                # If no query tags, fall back to confidence ordering
                if not q_tags:
                    score = 0
                scored.append((score, row.confidence or 0.0, row))

            scored.sort(key=lambda x: (x[0], x[1]), reverse=True)

            return [
                {
                    "id": row.id,
                    "entry_type": row.entry_type,
                    "content": row.content,
                    "tags": row.tags or [],
                    "confidence": row.confidence or 0.0,
                    "source_session_ids": row.source_session_ids or [],
                }
                for _, _, row in scored[:limit]
            ]
        except Exception as exc:
            logger.warning(f"VaultRetriever.get_relevant_entries failed: {exc!r}")
            return []
