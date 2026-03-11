"""Tests for app/core/ai_cache.py — fingerprint helpers and TTL validation."""

from datetime import datetime, timedelta

import pytest

from app.core.ai_cache import (
    CACHE_TTL_DAYS,
    cache_valid_until,
    deep_summary_fingerprint,
    is_cache_valid,
    prep_fingerprint,
    summary_dedup_fingerprint,
    treatment_plan_fingerprint,
)
from app.core.fingerprint import compute_fingerprint


# ── is_cache_valid ────────────────────────────────────────────────────────────

def test_is_cache_valid_none():
    assert is_cache_valid(None) is False


def test_is_cache_valid_past():
    past = datetime.utcnow() - timedelta(seconds=1)
    assert is_cache_valid(past) is False


def test_is_cache_valid_future():
    future = datetime.utcnow() + timedelta(hours=1)
    assert is_cache_valid(future) is True


def test_cache_valid_until_in_future():
    vut = cache_valid_until()
    assert vut > datetime.utcnow()
    # Should be approximately CACHE_TTL_DAYS away
    expected = datetime.utcnow() + timedelta(days=CACHE_TTL_DAYS)
    assert abs((vut - expected).total_seconds()) < 5


# ── prep_fingerprint ──────────────────────────────────────────────────────────

def _summaries(n: int) -> list[dict]:
    return [
        {
            "summary_id": i,
            "approved_at": f"2025-01-{i:02d}",
            "full_summary": f"Summary {i}",
        }
        for i in range(1, n + 1)
    ]


def test_prep_fingerprint_deterministic():
    s = _summaries(3)
    fp1 = prep_fingerprint("concise", s, style_version=1)
    fp2 = prep_fingerprint("concise", s, style_version=1)
    assert fp1 == fp2


def test_prep_fingerprint_mode_affects_hash():
    s = _summaries(2)
    assert prep_fingerprint("concise", s, 1) != prep_fingerprint("deep", s, 1)


def test_prep_fingerprint_style_version_affects_hash():
    s = _summaries(2)
    assert prep_fingerprint("concise", s, 1) != prep_fingerprint("concise", s, 2)


def test_prep_fingerprint_changed_summary():
    s1 = _summaries(3)
    s2 = _summaries(3)
    s2[0]["full_summary"] = "Completely different text"
    assert prep_fingerprint("concise", s1, 1) != prep_fingerprint("concise", s2, 1)


def test_prep_fingerprint_trims_to_10():
    """Only the last 10 summaries should affect the fingerprint."""
    many = _summaries(15)
    last10 = _summaries(15)[-10:]
    # Build a list where first 5 differ but last 10 are identical
    different_first5 = [
        {"summary_id": 99 + i, "approved_at": "2020-01-01", "full_summary": f"Old {i}"}
        for i in range(5)
    ] + last10
    assert prep_fingerprint("concise", many, 1) == prep_fingerprint("concise", different_first5, 1)


# ── summary_dedup_fingerprint ─────────────────────────────────────────────────

def test_summary_dedup_deterministic():
    fp1 = summary_dedup_fingerprint("therapist notes here", style_version=1)
    fp2 = summary_dedup_fingerprint("therapist notes here", style_version=1)
    assert fp1 == fp2


def test_summary_dedup_whitespace_stripped():
    fp1 = summary_dedup_fingerprint("notes", style_version=1)
    fp2 = summary_dedup_fingerprint("  notes  ", style_version=1)
    assert fp1 == fp2


def test_summary_dedup_different_notes():
    assert (
        summary_dedup_fingerprint("notes A", 1)
        != summary_dedup_fingerprint("notes B", 1)
    )


def test_summary_dedup_different_style_version():
    assert (
        summary_dedup_fingerprint("notes", 1)
        != summary_dedup_fingerprint("notes", 2)
    )


# ── deep_summary_fingerprint ──────────────────────────────────────────────────

def _ds_summaries(n: int) -> list[dict]:
    return [
        {
            "session_id": i,
            "session_date": f"2025-01-{i:02d}",
            "full_summary": f"Full summary {i}",
        }
        for i in range(1, n + 1)
    ]


def test_deep_summary_fingerprint_deterministic():
    s = _ds_summaries(4)
    assert deep_summary_fingerprint(s) == deep_summary_fingerprint(s)


def test_deep_summary_fingerprint_order_independent():
    """Summaries sorted by session_date so insertion order doesn't matter."""
    s = _ds_summaries(3)
    s_rev = list(reversed(s))
    assert deep_summary_fingerprint(s) == deep_summary_fingerprint(s_rev)


def test_deep_summary_fingerprint_new_summary_changes_hash():
    s3 = _ds_summaries(3)
    s4 = _ds_summaries(4)
    assert deep_summary_fingerprint(s3) != deep_summary_fingerprint(s4)


def test_deep_summary_fingerprint_changed_content():
    s1 = _ds_summaries(3)
    s2 = _ds_summaries(3)
    s2[1]["full_summary"] = "Edited text"
    assert deep_summary_fingerprint(s1) != deep_summary_fingerprint(s2)


# ── treatment_plan_fingerprint ────────────────────────────────────────────────

def _tp_summaries(n: int) -> list[dict]:
    return [
        {
            "session_date": f"2025-01-{i:02d}",
            "full_summary": f"Full summary {i}",
            "topics_discussed": ["topic A"],
            "next_session_plan": "Plan X",
        }
        for i in range(1, n + 1)
    ]


def test_treatment_plan_fingerprint_deterministic():
    s = _tp_summaries(3)
    assert treatment_plan_fingerprint(s) == treatment_plan_fingerprint(s)


def test_treatment_plan_fingerprint_order_independent():
    s = _tp_summaries(3)
    assert treatment_plan_fingerprint(s) == treatment_plan_fingerprint(list(reversed(s)))


def test_treatment_plan_fingerprint_different_from_deep_summary():
    """The two fingerprint functions should not collide for the same input data."""
    s_ds = _ds_summaries(3)
    s_tp = _tp_summaries(3)
    # They use different payload shapes, so hashes differ even with same count
    assert deep_summary_fingerprint(s_ds) != treatment_plan_fingerprint(s_tp)
