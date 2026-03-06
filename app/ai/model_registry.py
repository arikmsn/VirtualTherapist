"""
Dynamic model registry — resolves the best available Anthropic model per tier.

Fallback chain (in priority order):
  1. Anthropic /v1/models API result (auto-updated on each startup)
  2. Env var override: AI_FAST_MODEL / AI_STANDARD_MODEL / AI_DEEP_MODEL
  3. Hardcoded defaults (same values as the config defaults)

Usage:
  # Called once at startup:
  await resolve_models(settings.ANTHROPIC_API_KEY)

  # Called per generation:
  model_id = get_model("fast")   # "standard" | "deep"
"""

from __future__ import annotations

import httpx
from loguru import logger

from app.core.config import settings


# ── Tier → model prefix mapping ───────────────────────────────────────────────

TIER_PREFIXES: dict[str, str] = {
    "fast":     "claude-haiku",
    "standard": "claude-sonnet",
    "deep":     "claude-opus",
}

# ── Hardcoded last-resort defaults ────────────────────────────────────────────
# Must match the config defaults so behaviour is identical before the API call.

_HARDCODED_DEFAULTS: dict[str, str] = {
    "fast":     "claude-haiku-4-5-20251001",
    "standard": "claude-sonnet-4-5-20250929",
    "deep":     "claude-opus-4-5-20251101",
}

# Module-level cache populated by resolve_models() at startup.
# Empty dict means "not yet resolved" — get_model() falls back to config.
_resolved: dict[str, str] = {}


# ── Public API ────────────────────────────────────────────────────────────────

async def resolve_models(api_key: str | None) -> None:
    """
    Fetch available Anthropic models and update the module-level cache.

    For each tier, selects the model whose ID starts with the tier prefix and
    has the lexicographically latest date suffix (e.g. "20251001" > "20250929").

    Safe to call on every startup — failure is logged and silently ignored so
    the app always starts even if the API is temporarily unreachable.
    """
    global _resolved

    if not api_key or not api_key.strip():
        logger.warning("[ModelRegistry] No ANTHROPIC_API_KEY — skipping model auto-resolution.")
        return

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://api.anthropic.com/v1/models",
                headers={
                    "x-api-key": api_key.strip(),
                    "anthropic-version": "2023-06-01",
                },
                timeout=5.0,
            )
            resp.raise_for_status()
            model_ids: list[str] = [m["id"] for m in resp.json().get("data", [])]

        new_map: dict[str, str] = {}
        for tier, prefix in TIER_PREFIXES.items():
            matches = sorted(
                [m for m in model_ids if m.startswith(prefix)],
                reverse=True,  # latest date suffix first
            )
            if matches:
                new_map[tier] = matches[0]

        if new_map:
            _resolved = new_map
            logger.info(
                f"[ModelRegistry] Auto-resolved models from API: "
                f"fast={new_map.get('fast')} "
                f"standard={new_map.get('standard')} "
                f"deep={new_map.get('deep')}"
            )
        else:
            logger.warning("[ModelRegistry] /v1/models returned no matching models — using config fallback.")

    except Exception as exc:
        logger.warning(f"[ModelRegistry] Could not fetch models from API ({exc!r}) — using config fallback.")


def get_model(tier: str) -> str:
    """
    Return the model ID for the given tier using the three-level fallback chain.

    1. API-resolved (populated by resolve_models at startup)
    2. Env var / config setting (AI_FAST_MODEL / AI_STANDARD_MODEL / AI_DEEP_MODEL)
    3. Hardcoded default
    """
    # 1. API result
    if tier in _resolved:
        return _resolved[tier]

    # 2. Config / env var
    config_value = {
        "fast":     settings.AI_FAST_MODEL,
        "standard": settings.AI_STANDARD_MODEL,
        "deep":     settings.AI_DEEP_MODEL,
    }.get(tier)
    if config_value:
        return config_value

    # 3. Hardcoded last-resort
    return _HARDCODED_DEFAULTS.get(tier, "claude-sonnet-4-6-20250929")


def get_resolved_map() -> dict[str, str]:
    """Return a copy of the current resolved map (for diagnostics / tests)."""
    return dict(_resolved)


def _reset_for_tests() -> None:
    """Clear the module cache — only for use in tests."""
    global _resolved
    _resolved = {}
