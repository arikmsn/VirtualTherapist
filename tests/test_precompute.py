"""Tests for the AI precompute + caching layer (app/services/precompute.py).

Covers:
  - _compute_patient_fingerprint: stable hash, sensitive to summary/protocol changes
  - get_or_compute_deep_summary: cache hit vs cache miss
  - get_or_compute_treatment_plan: cache hit vs cache miss (create / update paths)
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
from datetime import datetime

from app.services.precompute import (
    _compute_patient_fingerprint,
    get_or_compute_deep_summary,
    get_or_compute_treatment_plan,
)
from app.core.fingerprint import FINGERPRINT_VERSION


# ---------------------------------------------------------------------------
# Helpers — lightweight mock DB that returns controlled query results
# ---------------------------------------------------------------------------

def _make_approved_summary_row(sid: int, updated_at: str):
    row = MagicMock()
    row.id = sid
    row.updated_at = updated_at
    return row


def _make_db(summary_rows=None, protocol_ids=None):
    """Build a minimal mock SQLAlchemy session for fingerprint tests."""
    db = MagicMock()

    # Simulate query chain: db.query(...).join(...).filter(...).order_by(...).all()
    approved_chain = MagicMock()
    approved_chain.all.return_value = summary_rows or []

    # Simulate query chain for protocol_ids: db.query(Patient.protocol_ids).filter(...).first()
    patient_row = MagicMock()
    patient_row.protocol_ids = protocol_ids or []
    protocol_chain = MagicMock()
    protocol_chain.filter.return_value = protocol_chain  # chain .filter().first()
    protocol_chain.first.return_value = patient_row

    def _query_router(*args, **kwargs):
        # Route based on whether the first arg is the protocol_ids column attribute
        if args and hasattr(args[0], 'key') and getattr(args[0], 'key', None) == 'protocol_ids':
            return protocol_chain
        # Default: return approved summary chain (join / filter / order_by / all)
        chain = MagicMock()
        chain.join.return_value = chain
        chain.filter.return_value = chain
        chain.order_by.return_value = approved_chain
        return chain

    db.query.side_effect = _query_router
    return db


def _make_deep_summary_orm(fingerprint=None, fp_version=FINGERPRINT_VERSION, created_at=None):
    ds = MagicMock()
    ds.id = 42
    ds.input_fingerprint = fingerprint
    ds.input_fingerprint_version = fp_version
    ds.created_at = created_at or datetime(2025, 1, 1)
    return ds


def _make_treatment_plan_orm(fingerprint=None, fp_version=FINGERPRINT_VERSION):
    plan = MagicMock()
    plan.id = 99
    plan.input_fingerprint = fingerprint
    plan.input_fingerprint_version = fp_version
    return plan


# ---------------------------------------------------------------------------
# _compute_patient_fingerprint tests
# ---------------------------------------------------------------------------

def test_fingerprint_stable_for_same_inputs():
    """Same approved summaries + same protocol_ids → identical fingerprint."""
    rows = [_make_approved_summary_row(1, "2025-01-10"), _make_approved_summary_row(2, "2025-02-01")]
    db = _make_db(summary_rows=rows, protocol_ids=["cbt_depression"])

    fp1 = _compute_patient_fingerprint(db, patient_id=7, therapist_id=3)
    fp2 = _compute_patient_fingerprint(db, patient_id=7, therapist_id=3)
    assert fp1 == fp2, "Fingerprint must be deterministic"


def test_fingerprint_changes_on_new_summary():
    """Adding a new approved summary changes the fingerprint."""
    rows_before = [_make_approved_summary_row(1, "2025-01-10")]
    rows_after = [
        _make_approved_summary_row(1, "2025-01-10"),
        _make_approved_summary_row(2, "2025-02-01"),
    ]

    db_before = _make_db(summary_rows=rows_before)
    db_after = _make_db(summary_rows=rows_after)

    fp_before = _compute_patient_fingerprint(db_before, patient_id=7, therapist_id=3)
    fp_after = _compute_patient_fingerprint(db_after, patient_id=7, therapist_id=3)
    assert fp_before != fp_after, "Fingerprint must change when a new summary is added"


def test_fingerprint_changes_on_protocol_update():
    """Changing protocol_ids changes the fingerprint."""
    rows = [_make_approved_summary_row(1, "2025-01-10")]

    db_a = _make_db(summary_rows=rows, protocol_ids=["cbt_depression"])
    db_b = _make_db(summary_rows=rows, protocol_ids=["cbt_depression", "act_general"])

    fp_a = _compute_patient_fingerprint(db_a, patient_id=7, therapist_id=3)
    fp_b = _compute_patient_fingerprint(db_b, patient_id=7, therapist_id=3)
    assert fp_a != fp_b, "Fingerprint must change when protocol_ids change"


def test_fingerprint_stable_when_protocols_reordered():
    """Protocol IDs are sorted before hashing — order should not matter."""
    rows = [_make_approved_summary_row(1, "2025-01-10")]

    db_a = _make_db(summary_rows=rows, protocol_ids=["act_general", "cbt_depression"])
    db_b = _make_db(summary_rows=rows, protocol_ids=["cbt_depression", "act_general"])

    fp_a = _compute_patient_fingerprint(db_a, patient_id=7, therapist_id=3)
    fp_b = _compute_patient_fingerprint(db_b, patient_id=7, therapist_id=3)
    assert fp_a == fp_b, "Protocol order must not affect fingerprint"


# ---------------------------------------------------------------------------
# get_or_compute_deep_summary — cache hit
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_deep_summary_cache_hit():
    """When the stored summary's fingerprint matches, no generation is called."""
    rows = [_make_approved_summary_row(1, "2025-01-10")]
    db = _make_db(summary_rows=rows)

    expected_fp = _compute_patient_fingerprint(db, patient_id=7, therapist_id=3)
    cached_ds = _make_deep_summary_orm(fingerprint=expected_fp)

    # db.query(DeepSummary).filter(...).order_by(...).first() → cached_ds
    ds_chain = MagicMock()
    ds_chain.filter.return_value = ds_chain
    ds_chain.order_by.return_value = ds_chain
    ds_chain.first.return_value = cached_ds

    original_side_effect = db.query.side_effect

    def _query_router_with_ds(*args, **kwargs):
        from app.models.deep_summary import DeepSummary
        if args and args[0] is DeepSummary:
            return ds_chain
        return original_side_effect(*args, **kwargs)

    db.query.side_effect = _query_router_with_ds

    mock_provider = MagicMock()

    with patch("app.services.precompute.DeepSummaryService") as MockService:
        result = await get_or_compute_deep_summary(
            db=db, patient_id=7, therapist_id=3, provider=mock_provider
        )

    assert result is cached_ds, "Cache hit must return the stored summary"
    MockService.return_value.generate_deep_summary.assert_not_called()


# ---------------------------------------------------------------------------
# get_or_compute_deep_summary — cache miss (new generation)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_deep_summary_cache_miss_generates_and_stores_fingerprint():
    """Cache miss (no stored summary) → pipeline called, fingerprint stored."""
    db = _make_db(summary_rows=[], protocol_ids=[])

    # No existing summary
    ds_chain = MagicMock()
    ds_chain.filter.return_value = ds_chain
    ds_chain.order_by.return_value = ds_chain
    ds_chain.first.return_value = None  # ← no cached entry

    original_side_effect = db.query.side_effect

    def _query_router_with_ds(*args, **kwargs):
        from app.models.deep_summary import DeepSummary
        if args and args[0] is DeepSummary:
            return ds_chain
        return original_side_effect(*args, **kwargs)

    db.query.side_effect = _query_router_with_ds

    new_ds = MagicMock()
    new_ds.input_fingerprint = None  # will be set by get_or_compute

    mock_provider = MagicMock()

    with patch("app.services.precompute.DeepSummaryService") as MockService:
        MockService.return_value.generate_deep_summary = AsyncMock(return_value=new_ds)
        result = await get_or_compute_deep_summary(
            db=db, patient_id=7, therapist_id=3, provider=mock_provider
        )

    assert result is new_ds
    MockService.return_value.generate_deep_summary.assert_called_once_with(
        patient_id=7, therapist_id=3, provider=mock_provider
    )
    # Fingerprint must have been written to the new artifact
    assert new_ds.input_fingerprint is not None, "Fingerprint must be stored on new summary"
    assert new_ds.input_fingerprint_version == FINGERPRINT_VERSION
    db.flush.assert_called()


# ---------------------------------------------------------------------------
# get_or_compute_treatment_plan — cache hit
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_treatment_plan_cache_hit():
    """When the active plan's fingerprint matches, no generation is called."""
    rows = [_make_approved_summary_row(1, "2025-01-10")]
    db = _make_db(summary_rows=rows)

    expected_fp = _compute_patient_fingerprint(db, patient_id=7, therapist_id=3)
    cached_plan = _make_treatment_plan_orm(fingerprint=expected_fp)

    mock_provider = MagicMock()

    with patch("app.services.precompute.TreatmentPlanService") as MockService:
        MockService.return_value.get_active_plan.return_value = cached_plan
        result = await get_or_compute_treatment_plan(
            db=db, patient_id=7, therapist_id=3, provider=mock_provider
        )

    assert result is cached_plan
    MockService.return_value.create_plan.assert_not_called()
    MockService.return_value.update_plan.assert_not_called()


# ---------------------------------------------------------------------------
# get_or_compute_treatment_plan — cache miss, no existing plan → create
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_treatment_plan_cache_miss_creates_new_plan():
    """Cache miss with no active plan → create_plan is called."""
    db = _make_db(summary_rows=[], protocol_ids=[])
    new_plan = MagicMock()
    new_plan.input_fingerprint = None

    mock_provider = MagicMock()

    with patch("app.services.precompute.TreatmentPlanService") as MockService:
        MockService.return_value.get_active_plan.return_value = None
        MockService.return_value.create_plan = AsyncMock(return_value=new_plan)
        result = await get_or_compute_treatment_plan(
            db=db, patient_id=7, therapist_id=3, provider=mock_provider
        )

    assert result is new_plan
    MockService.return_value.create_plan.assert_called_once()
    MockService.return_value.update_plan.assert_not_called()
    assert new_plan.input_fingerprint is not None
    assert new_plan.input_fingerprint_version == FINGERPRINT_VERSION


# ---------------------------------------------------------------------------
# get_or_compute_treatment_plan — stale plan → update
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_treatment_plan_stale_triggers_update():
    """Cache miss with an existing but stale plan → update_plan is called."""
    db = _make_db(summary_rows=[], protocol_ids=[])
    stale_plan = _make_treatment_plan_orm(fingerprint="stale_fp_that_does_not_match")
    updated_plan = MagicMock()
    updated_plan.input_fingerprint = None

    mock_provider = MagicMock()

    with patch("app.services.precompute.TreatmentPlanService") as MockService:
        MockService.return_value.get_active_plan.return_value = stale_plan
        MockService.return_value.update_plan = AsyncMock(return_value=updated_plan)
        result = await get_or_compute_treatment_plan(
            db=db, patient_id=7, therapist_id=3, provider=mock_provider
        )

    assert result is updated_plan
    MockService.return_value.update_plan.assert_called_once()
    MockService.return_value.create_plan.assert_not_called()
    assert updated_plan.input_fingerprint is not None
