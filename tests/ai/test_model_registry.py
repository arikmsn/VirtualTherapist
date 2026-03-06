"""
Dynamic model registry tests.

Tests:
 1. test_model_registry_fallback — API 500 → falls back to config values, no crash
 2. test_model_registry_resolves_latest — API returns multiple versions → picks latest
 3. test_model_registry_missing_key — no API key → skips resolve, returns config fallback
 4. test_get_model_before_resolve — _resolved empty → returns config/hardcoded value
 5. test_tier_to_model_uses_registry — ModelRouter reads from registry after resolve
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import httpx

from app.ai.model_registry import (
    resolve_models,
    get_model,
    get_resolved_map,
    _reset_for_tests,
    _HARDCODED_DEFAULTS,
)
from app.ai.models import FlowType
from app.core.config import settings


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def reset_registry():
    """Clear module-level cache before and after each test — prevents bleed."""
    _reset_for_tests()
    yield
    _reset_for_tests()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _anthropic_response(model_ids: list[str]) -> MagicMock:
    """Build a mock httpx Response returning the given model IDs."""
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {"data": [{"id": mid} for mid in model_ids]}
    return resp


# ── Test 1: API failure → fallback to config values ──────────────────────────

@pytest.mark.asyncio
async def test_model_registry_fallback():
    """
    If the Anthropic /v1/models API returns 500, resolve_models() logs a warning
    and returns without crashing. get_model() then falls back to config values.
    """
    async def _raise(*args, **kwargs):
        raise httpx.HTTPStatusError(
            "500 Internal Server Error",
            request=MagicMock(),
            response=MagicMock(status_code=500),
        )

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(side_effect=_raise)

    with patch("app.ai.model_registry.httpx.AsyncClient", return_value=mock_client):
        await resolve_models("sk-test-key")

    # _resolved should still be empty after failure
    assert get_resolved_map() == {}

    # get_model() must return a non-empty string (config or hardcoded fallback)
    fast = get_model("fast")
    standard = get_model("standard")
    deep = get_model("deep")

    assert fast == settings.AI_FAST_MODEL
    assert standard == settings.AI_STANDARD_MODEL
    assert deep == settings.AI_DEEP_MODEL

    # And they must be non-empty strings (never crash)
    assert isinstance(fast, str) and fast
    assert isinstance(standard, str) and standard
    assert isinstance(deep, str) and deep


# ── Test 2: API success → picks lexicographically latest per tier ─────────────

@pytest.mark.asyncio
async def test_model_registry_resolves_latest():
    """
    API returns multiple versions of haiku/sonnet/opus.
    resolve_models() picks the one with the latest date suffix per tier.
    """
    model_ids = [
        "claude-haiku-4-5-20251001",
        "claude-haiku-4-5-20250901",      # older haiku → should NOT be chosen
        "claude-sonnet-4-6-20250929",
        "claude-sonnet-4-5-20250601",     # older sonnet → should NOT be chosen
        "claude-opus-4-6-20251101",
        "claude-opus-4-5-20250501",       # older opus → should NOT be chosen
        "claude-3-opus-20240229",         # old-format — prefix doesn't match
    ]
    resp = _anthropic_response(model_ids)

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=resp)

    with patch("app.ai.model_registry.httpx.AsyncClient", return_value=mock_client):
        await resolve_models("sk-test-key")

    resolved = get_resolved_map()
    assert resolved["fast"] == "claude-haiku-4-5-20251001"
    assert resolved["standard"] == "claude-sonnet-4-6-20250929"
    assert resolved["deep"] == "claude-opus-4-6-20251101"

    # get_model() should now return the API-resolved IDs
    assert get_model("fast") == "claude-haiku-4-5-20251001"
    assert get_model("standard") == "claude-sonnet-4-6-20250929"
    assert get_model("deep") == "claude-opus-4-6-20251101"


# ── Test 3: Missing API key → skips resolve, returns config fallback ──────────

@pytest.mark.asyncio
async def test_model_registry_missing_key():
    """If no API key is provided, resolve_models() is a no-op."""
    with patch("app.ai.model_registry.httpx.AsyncClient") as MockClient:
        await resolve_models(None)
        MockClient.assert_not_called()   # no HTTP call made

    assert get_resolved_map() == {}
    # Still returns a valid model string
    assert get_model("fast") == settings.AI_FAST_MODEL


# ── Test 4: get_model before resolve → config/hardcoded values ───────────────

def test_get_model_before_resolve():
    """
    When the registry has not been populated (e.g. during tests that don't call
    resolve_models), get_model() returns the config value, not None or empty.
    """
    # All three tiers must return non-empty strings
    for tier in ("fast", "standard", "deep"):
        result = get_model(tier)
        assert isinstance(result, str) and result, f"get_model('{tier}') returned empty"


# ── Test 5: ModelRouter uses registry after resolve ───────────────────────────

@pytest.mark.asyncio
async def test_tier_to_model_uses_registry():
    """
    After resolve_models() populates the cache, ModelRouter.resolve() returns
    the API-resolved model IDs rather than the hardcoded config values.
    """
    new_fast = "claude-haiku-5-0-20260101"  # hypothetical future model
    new_standard = "claude-sonnet-5-0-20260101"
    new_deep = "claude-opus-5-0-20260101"

    model_ids = [new_fast, new_standard, new_deep]
    resp = _anthropic_response(model_ids)

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=resp)

    with patch("app.ai.model_registry.httpx.AsyncClient", return_value=mock_client):
        await resolve_models("sk-test-key")

    from app.ai.router import ModelRouter
    router = ModelRouter()

    fast_id, _ = router.resolve(FlowType.COMPLETENESS_CHECK)
    std_id, _ = router.resolve(FlowType.SESSION_SUMMARY)
    deep_id, _ = router.resolve(FlowType.FORMAL_RECORD)

    assert fast_id == new_fast
    assert std_id == new_standard
    assert deep_id == new_deep
