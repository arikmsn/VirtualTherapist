"""
Strict typed response models for the summary task layer (Phase 10).

Each AI summary task has its OWN response model with extra="forbid" so that a
malformed or hallucinated model response (e.g. a suggest call that tries to
return rewritten summary text) fails validation and is rejected by parse_strict()
rather than silently leaking into the therapist's draft.

These are deliberately separate from the loose SessionSummary persistence shape —
the whole point of the refactor is that each task means something different.
"""

from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


# ── source_save ───────────────────────────────────────────────────────────────

class SourceSaveResult(BaseModel):
    """Result of a non-AI save-as-is. Documents that no model was called."""
    model_config = ConfigDict(extra="forbid")

    saved: bool
    char_count: int


# ── source_summary_suggest ────────────────────────────────────────────────────

class Suggestion(BaseModel):
    """A single advisory note TO the therapist. Never replacement text."""
    model_config = ConfigDict(extra="forbid")

    category: Literal["missing", "clarify", "risk", "structure", "other"]
    text: str = Field(..., description="concise advisory note; not a rewrite")
    severity: Literal["info", "important"] = "info"


class SuggestResult(BaseModel):
    """
    Advisory-only output. Intentionally has NO field that can carry a rewritten
    summary — extra="forbid" means a response with e.g. `rewritten_summary` is
    rejected outright.
    """
    model_config = ConfigDict(extra="forbid")

    suggestions: List[Suggestion]
    overall_note: Optional[str] = None


# ── ai_summary_revise ─────────────────────────────────────────────────────────

class ReviseResult(BaseModel):
    """Single-shot revision output: the revised draft plus a one-line change note."""
    model_config = ConfigDict(extra="forbid")

    revised_summary: str
    change_note: Optional[str] = None
    confidence: float = 0.0
