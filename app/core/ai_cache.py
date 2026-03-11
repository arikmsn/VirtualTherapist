"""AI precompute cache helpers.

TTL-based cache for AI features:
  - Prep (session preparation) — fingerprint + 7-day TTL on sessions row
  - Session Summary            — dedup guard: same notes → same fingerprint → skip LLM
  - Deep Summary               — precompute stored on patient row; 7-day TTL
  - Treatment Plan             — precompute stored on patient row; 7-day TTL

Fingerprint logic lives here so the version bump (FINGERPRINT_VERSION) and
the payload schema are both in one place.  Bump FINGERPRINT_VERSION when any
input payload changes (new fields added, field renamed, etc.).
"""

from datetime import datetime, timedelta
from typing import Optional

from app.core.fingerprint import FINGERPRINT_VERSION, compute_fingerprint

# How long a background-precomputed result stays valid.
# Manual triggers always bypass this TTL and re-compute.
CACHE_TTL_DAYS = 7


# ── TTL helpers ───────────────────────────────────────────────────────────────

def cache_valid_until() -> datetime:
    """Return the expiry datetime for a freshly populated cache entry."""
    return datetime.utcnow() + timedelta(days=CACHE_TTL_DAYS)


def is_cache_valid(valid_until: Optional[datetime]) -> bool:
    """Return True iff valid_until is set and has not expired."""
    if valid_until is None:
        return False
    return datetime.utcnow() < valid_until


# ── Fingerprint builders ──────────────────────────────────────────────────────

def prep_fingerprint(mode: str, approved_summaries: list[dict], style_version: int) -> str:
    """
    Canonical fingerprint for a prep brief generation.

    Matches the fingerprint stored in sessions.prep_input_fingerprint.
    Payload: mode, last-10 approved summaries (summary_id, approved_at, full_summary),
    and the therapist style_version.
    """
    payload = {
        "mode": mode,
        "summaries": [
            {
                "summary_id": s.get("summary_id"),
                "approved_at": s.get("approved_at"),
                "full_summary": s.get("full_summary", ""),
            }
            for s in approved_summaries
        ][-10:],
        "style_version": style_version,
    }
    return compute_fingerprint(payload)


def summary_dedup_fingerprint(notes_text: str, style_version: int) -> str:
    """
    Deduplication fingerprint for session summaries.

    Stored in session_summaries.ai_input_fingerprint.
    If the therapist submits identical notes within TTL, return the existing
    summary row instead of re-calling the LLM.
    """
    return compute_fingerprint({
        "notes": notes_text.strip(),
        "style_version": style_version,
        "v": FINGERPRINT_VERSION,
    })


def deep_summary_fingerprint(approved_summaries: list[dict]) -> str:
    """
    Canonical fingerprint for a deep summary generation.

    Stored in patients.deep_summary_cache_fingerprint.
    Payload: session_id, session_date, and full_summary for every approved summary,
    sorted by session_date so order doesn't matter.
    """
    entries = sorted(
        [
            {
                "session_id": s.get("session_id"),
                "session_date": s.get("session_date", ""),
                "full_summary": s.get("full_summary", ""),
            }
            for s in approved_summaries
        ],
        key=lambda x: x["session_date"],
    )
    return compute_fingerprint({"summaries": entries, "v": FINGERPRINT_VERSION})


def treatment_plan_fingerprint(approved_summaries: list[dict]) -> str:
    """
    Canonical fingerprint for a treatment plan generation.

    Stored in patients.treatment_plan_cache_fingerprint.
    Payload mirrors deep_summary_fingerprint but with treatment-plan-relevant fields.
    """
    entries = sorted(
        [
            {
                "session_date": s.get("session_date", ""),
                "full_summary": s.get("full_summary", ""),
                "topics_discussed": s.get("topics_discussed") or [],
                "next_session_plan": s.get("next_session_plan") or "",
            }
            for s in approved_summaries
        ],
        key=lambda x: x["session_date"],
    )
    return compute_fingerprint({"summaries": entries, "v": FINGERPRINT_VERSION})
