"""
Phase 8 — Deep Summary + Therapist Reference Vault tests.

12 tests:
  1. Source-of-truth — only approved summaries used
  2. Zero approved summaries → Hebrew fallback, no LLM call
  3. Short history (< 5 sessions) → 2 LLM calls (no synthesis)
  4. Medium history (5–10 sessions) → 3 LLM calls (+ synthesis step)
  5. Long history (> 10 sessions) → N+2 LLM calls (chunk extractions + synthesis + render)
  6. Vault context injected in rendering call only
  7. VaultRetriever tag-intersection scoring
  8. Vault deduplication — identical content skipped
  9. Vault per-client cap enforced (max 15 entries)
 10. DeepSummaryService.generate_deep_summary stores DeepSummary row
 11. approve_deep_summary sets status and approved_at
 12. Telemetry — DEEP_SUMMARY + VAULT_EXTRACTION log rows written
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest

from app.ai.deep_summary import (
    DeepSummaryPipeline,
    DeepSummaryInput,
    DeepSummaryResult,
    VaultExtractor,
    VaultRetriever,
    VaultEntry,
    VaultEntryType,
    _build_chunk_extraction_user,
    _build_render_user,
    _SHORT_HISTORY_THRESHOLD,
    _CHUNK_SIZE,
    _MAX_VAULT_ENTRIES,
    _ZERO_APPROVED_HEBREW,
)
from app.ai.models import FlowType
from app.core.config import settings


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_summary(n: int, full_summary: str = "סיכום מאושר") -> dict:
    return {
        "session_date": f"2026-0{min(n, 9)}-01",
        "session_number": n,
        "session_id": 100 + n,
        "full_summary": full_summary,
        "topics_discussed": [f"נושא {n}"],
        "homework_assigned": [],
        "next_session_plan": "להמשיך",
        "risk_assessment": None,
        "mood_observed": "רגוע",
    }


def _make_summary_json(n_sessions: int = 3) -> dict:
    return {
        "arc_narrative": f"נרטיב של {n_sessions} פגישות",
        "presenting_problem_evolution": "חרדה ירדה",
        "treatment_phases": [],
        "goals_outcome": [],
        "clinical_patterns_identified": ["דפוס הימנעות"],
        "turning_points": [],
        "what_worked": ["CBT"],
        "what_didnt_work": [],
        "current_status": "יציב",
        "recommendations_going_forward": ["המשך עבודה"],
        "sessions_covered": n_sessions,
        "confidence": 0.85,
    }


def _make_generation_result(content: str, flow_type: FlowType, model: str = None) -> "GenerationResult":
    from app.ai.models import GenerationResult
    return GenerationResult(
        content=content,
        model_used=model or settings.AI_DEEP_MODEL,
        provider="test",
        flow_type=flow_type,
        prompt_tokens=200,
        completion_tokens=100,
        route_reason=f"flow:{flow_type.value},tier:deep",
    )


def _make_provider_for_n_summaries(n: int, render_text: str = "נרטיב קליני עמוק") -> MagicMock:
    """Build a provider mock with appropriate number of side_effect responses."""
    from app.ai.models import GenerationResult

    summary_json_str = json.dumps(_make_summary_json(n), ensure_ascii=False)

    provider = MagicMock()

    if n < _SHORT_HISTORY_THRESHOLD:
        # 2 calls: extraction + render
        provider.generate = AsyncMock(side_effect=[
            _make_generation_result(summary_json_str, FlowType.DEEP_SUMMARY),
            _make_generation_result(render_text, FlowType.DEEP_SUMMARY),
        ])
    else:
        # N chunks + synthesis + render
        n_chunks = (n + _CHUNK_SIZE - 1) // _CHUNK_SIZE
        responses = []
        for _ in range(n_chunks):
            responses.append(_make_generation_result(summary_json_str, FlowType.DEEP_SUMMARY))
        # synthesis
        responses.append(_make_generation_result(summary_json_str, FlowType.DEEP_SUMMARY))
        # render
        responses.append(_make_generation_result(render_text, FlowType.DEEP_SUMMARY))
        provider.generate = AsyncMock(side_effect=responses)

    return provider


def _make_vault_provider(entries: list = None) -> MagicMock:
    """Provider that returns vault entries from VAULT_EXTRACTION flow."""
    from app.ai.models import GenerationResult
    data = entries or [
        {
            "entry_type": "clinical_pattern",
            "content": "דפוס הימנעות חברתית בולט",
            "tags": ["הימנעות", "חרדה"],
            "confidence": 0.9,
            "source_session_ids": [101, 102],
        }
    ]
    provider = MagicMock()
    provider.generate = AsyncMock(return_value=GenerationResult(
        content=json.dumps(data, ensure_ascii=False),
        model_used=settings.AI_STANDARD_MODEL,
        provider="test",
        flow_type=FlowType.VAULT_EXTRACTION,
        prompt_tokens=150,
        completion_tokens=80,
        route_reason="flow:vault_extraction,tier:standard",
    ))
    return provider


def _make_inp(n_sessions: int = 3, vault_context: Optional[str] = None) -> DeepSummaryInput:
    summaries = [_make_summary(i) for i in range(1, n_sessions + 1)]
    return DeepSummaryInput(
        client_id=1,
        therapist_id=2,
        modality="cbt",
        approved_summaries=summaries,
        treatment_plan=None,
        therapist_signature=None,
    )


# ── Test 1: Source-of-truth ───────────────────────────────────────────────────

def test_deep_summary_source_of_truth():
    """Chunk extraction user prompt contains ONLY the sessions passed in approved_summaries."""
    summaries = [_make_summary(i, f"סיכום מאושר {i}") for i in range(1, 4)]
    prompt = _build_chunk_extraction_user(summaries, 0, 1)

    assert "Session #1" in prompt
    assert "Session #2" in prompt
    assert "Session #3" in prompt
    assert "סיכום מאושר 1" in prompt
    assert "סיכום מאושר 3" in prompt


# ── Test 2: Zero approved summaries → fallback ───────────────────────────────

@pytest.mark.asyncio
async def test_deep_summary_zero_approved():
    """Zero approved summaries → Hebrew fallback, no LLM call."""
    provider = _make_provider_for_n_summaries(3)
    pipeline = DeepSummaryPipeline(provider)

    inp = _make_inp(n_sessions=0)
    result = await pipeline.run(inp)

    assert result.rendered_text == _ZERO_APPROVED_HEBREW
    assert result.summary_json == {}
    assert result.model_used == "none"
    assert result.tokens_used == 0
    provider.generate.assert_not_called()


# ── Test 3: Short history (< 5 sessions) → 2 calls ───────────────────────────

@pytest.mark.asyncio
async def test_short_history_two_calls():
    """< _SHORT_HISTORY_THRESHOLD sessions → exactly 2 LLM calls (extraction + render)."""
    n = _SHORT_HISTORY_THRESHOLD - 1   # e.g. 4
    provider = _make_provider_for_n_summaries(n)
    pipeline = DeepSummaryPipeline(provider)

    inp = _make_inp(n_sessions=n)
    result = await pipeline.run(inp)

    assert provider.generate.call_count == 2
    # No synthesis step → _synthesis_result is None
    assert pipeline._synthesis_result is None
    assert len(pipeline._extraction_results) == 1
    assert pipeline._render_result is not None
    assert isinstance(result.rendered_text, str)
    assert len(result.rendered_text) > 0


# ── Test 4: Medium history (5–10 sessions) → 3 calls ─────────────────────────

@pytest.mark.asyncio
async def test_medium_history_three_calls():
    """5–10 sessions → exactly 3 LLM calls (1 extraction + synthesis + render)."""
    n = _SHORT_HISTORY_THRESHOLD   # exactly 5 (fits in one chunk, but >= threshold)
    provider = _make_provider_for_n_summaries(n)
    pipeline = DeepSummaryPipeline(provider)

    inp = _make_inp(n_sessions=n)
    result = await pipeline.run(inp)

    # Exactly 3 calls: 1 chunk extraction + 1 synthesis + 1 render
    assert provider.generate.call_count == 3
    assert len(pipeline._extraction_results) == 1
    assert pipeline._synthesis_result is not None
    assert pipeline._render_result is not None


# ── Test 5: Long history (> 10 sessions) → N+2 calls ─────────────────────────

@pytest.mark.asyncio
async def test_long_history_chunked_calls():
    """12 sessions → 2 chunk extractions + synthesis + render = 4 calls."""
    n = _CHUNK_SIZE + 2   # e.g. 12 → 2 chunks
    provider = _make_provider_for_n_summaries(n)
    pipeline = DeepSummaryPipeline(provider)

    inp = _make_inp(n_sessions=n)
    result = await pipeline.run(inp)

    expected_chunks = 2   # ceil(12 / 10) = 2
    expected_calls = expected_chunks + 1 + 1   # chunks + synthesis + render
    assert provider.generate.call_count == expected_calls
    assert len(pipeline._extraction_results) == expected_chunks
    assert pipeline._synthesis_result is not None


# ── Test 6: Vault context injected in render call only ───────────────────────

@pytest.mark.asyncio
async def test_vault_context_in_render_only():
    """Vault context appears in render call user message, not in extraction call."""
    vault_context = "תובנות קליניות מהכספת:\nדפוס הימנעות"

    n = 3
    provider = _make_provider_for_n_summaries(n)
    pipeline = DeepSummaryPipeline(provider)

    inp = _make_inp(n_sessions=n)
    await pipeline.run(inp, vault_context=vault_context)

    assert provider.generate.call_count == 2

    # First call = extraction — no vault context in messages
    first_call_messages = provider.generate.call_args_list[0].kwargs.get("messages") or \
                          provider.generate.call_args_list[0].args[0]
    first_call_content = " ".join(m["content"] for m in first_call_messages)
    assert "כספת" not in first_call_content

    # Second call = render — vault context present
    second_call_messages = provider.generate.call_args_list[1].kwargs.get("messages") or \
                           provider.generate.call_args_list[1].args[0]
    second_call_content = " ".join(m["content"] for m in second_call_messages)
    assert "כספת" in second_call_content


# ── Test 7: VaultRetriever tag-intersection scoring ───────────────────────────

@pytest.mark.asyncio
async def test_vault_retriever_tag_scoring():
    """VaultRetriever ranks entries by tag intersection with query tags."""
    high_match = MagicMock()
    high_match.id = 1
    high_match.entry_type = "clinical_pattern"
    high_match.content = "דפוס הימנעות"
    high_match.tags = ["הימנעות", "חרדה", "CBT"]
    high_match.confidence = 0.8
    high_match.source_session_ids = [101]

    low_match = MagicMock()
    low_match.id = 2
    low_match.entry_type = "diagnostic_note"
    low_match.content = "היפוכים רגשיים"
    low_match.tags = ["דיכאון"]
    low_match.confidence = 0.9
    low_match.source_session_ids = [102]

    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = [low_match, high_match]

    retriever = VaultRetriever(db)
    entries = await retriever.get_relevant_entries(
        client_id=1,
        therapist_id=2,
        query_tags=["הימנעות", "חרדה"],
        limit=5,
    )

    assert len(entries) == 2
    # High-match entry (2 tag overlaps) should rank first
    assert entries[0]["id"] == high_match.id
    assert entries[1]["id"] == low_match.id


# ── Test 8: Vault deduplication ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_vault_deduplication():
    """DeepSummaryService skips vault entries with content already in DB."""
    from app.services.deep_summary_service import DeepSummaryService

    existing_content = "דפוס הימנעות חברתית בולט"
    duplicate_entry = {
        "entry_type": "clinical_pattern",
        "content": existing_content,
        "tags": ["הימנעות"],
        "confidence": 0.9,
        "source_session_ids": [101],
    }

    # DB returns existing content for dedup check
    existing_row = MagicMock()
    existing_row.content = existing_content

    db = MagicMock()
    # count query
    db.query.return_value.filter.return_value.count.return_value = 2
    # content query for dedup
    db.query.return_value.filter.return_value.all.return_value = [existing_row]
    db.add = MagicMock()
    db.flush = MagicMock()

    vault_provider = _make_vault_provider([duplicate_entry])

    service = DeepSummaryService(db)

    vault_rows_added = []
    def capture_vault_add(obj):
        from app.models.reference_vault import TherapistReferenceVault
        if isinstance(obj, TherapistReferenceVault):
            vault_rows_added.append(obj)
    db.add.side_effect = capture_vault_add

    with patch.object(service, "_write_generation_log"):
        stored = await service._extract_and_store_vault_entries(
            summary_json=_make_summary_json(),
            client_id=1,
            therapist_id=2,
            source_session_ids=[101],
            provider=vault_provider,
        )

    # Duplicate should be skipped — no vault entries stored
    assert stored == 0
    assert len(vault_rows_added) == 0


# ── Test 9: Vault per-client cap enforced ─────────────────────────────────────

@pytest.mark.asyncio
async def test_vault_cap_enforced():
    """DeepSummaryService stops storing when client already has _MAX_VAULT_ENTRIES entries."""
    from app.services.deep_summary_service import DeepSummaryService

    # Client already at cap
    db = MagicMock()
    db.query.return_value.filter.return_value.count.return_value = _MAX_VAULT_ENTRIES
    db.query.return_value.filter.return_value.all.return_value = []  # no existing content
    db.add = MagicMock()
    db.flush = MagicMock()

    new_entries = [
        {
            "entry_type": "clinical_pattern",
            "content": f"תובנה חדשה {i}",
            "tags": [],
            "confidence": 0.8,
            "source_session_ids": [],
        }
        for i in range(3)
    ]
    vault_provider = _make_vault_provider(new_entries)

    service = DeepSummaryService(db)

    vault_rows_added = []
    def capture_vault_add(obj):
        from app.models.reference_vault import TherapistReferenceVault
        if isinstance(obj, TherapistReferenceVault):
            vault_rows_added.append(obj)
    db.add.side_effect = capture_vault_add

    with patch.object(service, "_write_generation_log"):
        stored = await service._extract_and_store_vault_entries(
            summary_json=_make_summary_json(),
            client_id=1,
            therapist_id=2,
            source_session_ids=[],
            provider=vault_provider,
        )

    assert stored == 0
    assert len(vault_rows_added) == 0


# ── Test 10: generate_deep_summary stores DeepSummary row ─────────────────────

@pytest.mark.asyncio
async def test_generate_deep_summary_stores_row():
    """DeepSummaryService.generate_deep_summary() adds a DeepSummary row to DB."""
    from app.services.deep_summary_service import DeepSummaryService
    from app.models.deep_summary import DeepSummary, DeepSummaryStatus

    mock_patient = MagicMock()
    mock_patient.id = 1
    mock_patient.therapist_id = 2

    mock_session_row = MagicMock()
    mock_session_row.session_date = "2026-01-01"
    mock_session_row.session_number = 1
    mock_session_row.id = 101
    mock_session_row.summary_id = 99
    mock_summary = MagicMock()
    mock_summary.approved_by_therapist = True
    mock_summary.full_summary = "סיכום פגישה"
    mock_summary.topics_discussed = ["נושא 1"]
    mock_summary.homework_assigned = []
    mock_summary.next_session_plan = None
    mock_summary.risk_assessment = None
    mock_summary.mood_observed = "רגוע"
    mock_session_row.summary = mock_summary

    mock_therapist = MagicMock()
    mock_therapist.full_name = "ד\"ר כהן"
    mock_profile = MagicMock()
    mock_profile.therapeutic_approach = MagicMock(value="cbt")

    db = MagicMock()
    # Patient check
    db.query.return_value.filter.return_value.first.side_effect = [
        mock_patient, mock_therapist, mock_profile,
    ]
    # Approved sessions query
    db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [
        mock_session_row
    ]
    # Vault retriever and count queries
    db.query.return_value.filter.return_value.all.return_value = []
    db.query.return_value.filter.return_value.count.return_value = 0
    db.add = MagicMock()
    db.flush = MagicMock()

    # 2-call provider (short history, 1 session < _SHORT_HISTORY_THRESHOLD)
    provider = _make_provider_for_n_summaries(1)
    # Vault extractor provider (returns empty entries)
    vault_provider = _make_vault_provider([])

    # The deep summary pipeline and vault extraction use the same provider arg
    # We need a combined provider that handles both flow types
    from app.ai.models import GenerationResult
    summary_json_str = json.dumps(_make_summary_json(1), ensure_ascii=False)
    combined_provider = MagicMock()
    combined_provider.generate = AsyncMock(side_effect=[
        # extraction call
        _make_generation_result(summary_json_str, FlowType.DEEP_SUMMARY),
        # render call
        _make_generation_result("נרטיב קליני עמוק", FlowType.DEEP_SUMMARY),
        # vault extraction call
        GenerationResult(
            content=json.dumps([], ensure_ascii=False),
            model_used=settings.AI_STANDARD_MODEL,
            provider="test",
            flow_type=FlowType.VAULT_EXTRACTION,
            prompt_tokens=100,
            completion_tokens=30,
            route_reason="flow:vault_extraction,tier:standard",
        ),
    ])

    service = DeepSummaryService(db)

    deep_summaries_added = []
    original_add = db.add.side_effect
    def capture_add(obj):
        if isinstance(obj, DeepSummary):
            deep_summaries_added.append(obj)
    db.add.side_effect = capture_add

    with patch("app.services.deep_summary_service.SignatureEngine") as MockSig:
        MockSig.return_value.get_active_profile = AsyncMock(return_value=None)
        with patch.object(service, "_write_generation_log"):
            result = await service.generate_deep_summary(
                patient_id=1,
                therapist_id=2,
                provider=combined_provider,
            )

    assert len(deep_summaries_added) == 1
    ds = deep_summaries_added[0]
    assert ds.status == DeepSummaryStatus.DRAFT.value
    assert ds.patient_id == 1
    assert ds.therapist_id == 2
    assert ds.sessions_covered == 1


# ── Test 11: approve_deep_summary sets status and approved_at ─────────────────

def test_approve_deep_summary():
    """approve_deep_summary() sets status=approved and approved_at."""
    from app.services.deep_summary_service import DeepSummaryService
    from app.models.deep_summary import DeepSummary, DeepSummaryStatus

    mock_summary = MagicMock(spec=DeepSummary)
    mock_summary.id = 42
    mock_summary.therapist_id = 2
    mock_summary.status = DeepSummaryStatus.DRAFT.value
    mock_summary.approved_at = None

    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = mock_summary
    db.flush = MagicMock()

    service = DeepSummaryService(db)
    result = service.approve_deep_summary(summary_id=42, therapist_id=2)

    assert result.status == DeepSummaryStatus.APPROVED.value
    assert result.approved_at is not None
    db.flush.assert_called_once()


# ── Test 12: Telemetry — DEEP_SUMMARY + VAULT_EXTRACTION logs ─────────────────

@pytest.mark.asyncio
async def test_deep_summary_telemetry():
    """
    generate_deep_summary writes DEEP_SUMMARY log rows for each pipeline call
    and a VAULT_EXTRACTION log row for the vault extraction call.
    """
    from app.services.deep_summary_service import DeepSummaryService

    mock_patient = MagicMock()
    mock_patient.id = 1
    mock_patient.therapist_id = 2

    mock_session_row = MagicMock()
    mock_session_row.session_date = "2026-01-01"
    mock_session_row.session_number = 1
    mock_session_row.id = 101
    mock_session_row.summary_id = 99
    mock_summary = MagicMock()
    mock_summary.approved_by_therapist = True
    mock_summary.full_summary = "סיכום"
    mock_summary.topics_discussed = []
    mock_summary.homework_assigned = []
    mock_summary.next_session_plan = None
    mock_summary.risk_assessment = None
    mock_summary.mood_observed = None
    mock_session_row.summary = mock_summary

    mock_therapist = MagicMock()
    mock_therapist.full_name = "ד\"ר לוי"
    mock_profile = MagicMock()
    mock_profile.therapeutic_approach = MagicMock(value="psychodynamic")

    db = MagicMock()
    db.query.return_value.filter.return_value.first.side_effect = [
        mock_patient, mock_therapist, mock_profile,
    ]
    db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [
        mock_session_row
    ]
    db.query.return_value.filter.return_value.all.return_value = []
    db.query.return_value.filter.return_value.count.return_value = 0
    db.add = MagicMock()
    db.flush = MagicMock()

    from app.ai.models import GenerationResult
    summary_json_str = json.dumps(_make_summary_json(1), ensure_ascii=False)
    provider = MagicMock()
    provider.generate = AsyncMock(side_effect=[
        _make_generation_result(summary_json_str, FlowType.DEEP_SUMMARY),
        _make_generation_result("נרטיב", FlowType.DEEP_SUMMARY),
        GenerationResult(
            content=json.dumps([], ensure_ascii=False),
            model_used=settings.AI_STANDARD_MODEL,
            provider="test",
            flow_type=FlowType.VAULT_EXTRACTION,
            prompt_tokens=100,
            completion_tokens=30,
            route_reason="flow:vault_extraction,tier:standard",
        ),
    ])

    service = DeepSummaryService(db)

    with patch("app.services.deep_summary_service.SignatureEngine") as MockSig:
        MockSig.return_value.get_active_profile = AsyncMock(return_value=None)
        with patch.object(service, "_write_generation_log") as mock_log:
            await service.generate_deep_summary(
                patient_id=1,
                therapist_id=2,
                provider=provider,
            )

    deep_calls = [
        c for c in mock_log.call_args_list
        if c.kwargs.get("flow_type") == FlowType.DEEP_SUMMARY
    ]
    vault_calls = [
        c for c in mock_log.call_args_list
        if c.kwargs.get("flow_type") == FlowType.VAULT_EXTRACTION
    ]

    # Short history → 1 extraction + 1 render = 2 DEEP_SUMMARY calls
    assert len(deep_calls) == 2, f"Expected 2 DEEP_SUMMARY log calls, got {len(deep_calls)}"
    # Vault extractor → 1 VAULT_EXTRACTION call (even if 0 entries returned)
    assert len(vault_calls) == 1, f"Expected 1 VAULT_EXTRACTION log call, got {len(vault_calls)}"
