"""
app.ai — Clean AI provider abstraction and model routing layer.

Public surface:
  AIProvider          — ABC; call provider.generate(messages, model, ...) → GenerationResult
  AnthropicProvider   — Anthropic Claude implementation (primary)
  OpenAIProvider      — OpenAI implementation (kept for Whisper callers; not used for text gen)
  ModelRouter         — Resolves flow_type + context → (model_id, route_reason)
  FlowType            — Enum of all generation flows
  GenerationResult    — Dataclass returned by every provider.generate() call

Usage:
  from app.ai import AnthropicProvider, ModelRouter, FlowType

  router   = ModelRouter()
  provider = AnthropicProvider(api_key=settings.ANTHROPIC_API_KEY)

  model_id, reason = router.resolve(FlowType.SESSION_SUMMARY, session_count=8)
  result = await provider.generate(messages, model=model_id)
"""

from app.ai.models import FlowType, GenerationResult
from app.ai.provider import AIProvider, AnthropicProvider, OpenAIProvider
from app.ai.router import ModelRouter

__all__ = [
    "FlowType",
    "GenerationResult",
    "AIProvider",
    "AnthropicProvider",
    "OpenAIProvider",
    "ModelRouter",
]
