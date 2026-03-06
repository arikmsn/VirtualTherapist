"""
AIProvider — abstract base + concrete implementations.

AnthropicProvider   — primary text generation (Claude models)
OpenAIProvider      — kept for Whisper callers; not used for text generation

Both implementations share the same interface:
  result = await provider.generate(messages, model, temperature, max_tokens)

messages is a list of OpenAI-style dicts:
  [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}]

AnthropicProvider splits the list into a system prompt + user/assistant turns
before calling the Anthropic Messages API, so callers never need to know
which underlying API format is used.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import AsyncIterator

from loguru import logger

from app.ai.models import FlowType, GenerationResult


class AIProvider(ABC):
    """Abstract base for all AI providers."""

    @abstractmethod
    async def generate(
        self,
        messages: list[dict],
        *,
        model: str,
        flow_type: FlowType,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        route_reason: str = "",
    ) -> GenerationResult:
        """
        Generate a completion from the given messages.

        Args:
            messages:     OpenAI-style list of {role, content} dicts.
                          role must be "system", "user", or "assistant".
            model:        The model ID to use (already resolved by ModelRouter).
            flow_type:    The generation flow — stored in GenerationResult for logging.
            temperature:  Sampling temperature.
            max_tokens:   Maximum output tokens.
            route_reason: Human-readable explanation of why this model was chosen.

        Returns:
            GenerationResult with content + telemetry fields populated.
        """


class AnthropicProvider(AIProvider):
    """
    Anthropic Claude implementation — primary text generation provider.

    Splits OpenAI-style message lists into system + user/assistant turns
    as required by the Anthropic Messages API.
    """

    def __init__(self, api_key: str) -> None:
        import anthropic
        self._client = anthropic.AsyncAnthropic(api_key=api_key)

    async def generate(
        self,
        messages: list[dict],
        *,
        model: str,
        flow_type: FlowType,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        route_reason: str = "",
    ) -> GenerationResult:
        start = time.monotonic()

        # Split system message from the conversation turns
        system_parts: list[str] = []
        turns: list[dict] = []
        for msg in messages:
            if msg["role"] == "system":
                system_parts.append(msg["content"])
            else:
                turns.append({"role": msg["role"], "content": msg["content"]})

        system_text = "\n\n".join(system_parts)

        kwargs: dict = dict(
            model=model,
            messages=turns,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        if system_text:
            kwargs["system"] = system_text

        estimated_ctx = sum(len(m.get("content", "")) for m in messages) // 4
        logger.info(
            f"[{flow_type.value}] model={model} context_tokens≈{estimated_ctx} reason={route_reason}"
        )

        response = await self._client.messages.create(**kwargs)

        elapsed_ms = int((time.monotonic() - start) * 1000)
        content = response.content[0].text if response.content else ""

        logger.info(
            f"[{flow_type.value}] done model={model} "
            f"in={response.usage.input_tokens} out={response.usage.output_tokens} "
            f"ms={elapsed_ms}"
        )

        return GenerationResult(
            content=content,
            model_used=model,
            provider="anthropic",
            flow_type=flow_type,
            prompt_tokens=response.usage.input_tokens,
            completion_tokens=response.usage.output_tokens,
            generation_ms=elapsed_ms,
            route_reason=route_reason,
        )


    async def generate_stream(
        self,
        messages: list[dict],
        *,
        model: str,
        flow_type: FlowType,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        route_reason: str = "",
    ) -> AsyncIterator[str]:
        """
        Stream token chunks from Anthropic.  Yields raw text fragments as they arrive.
        Does NOT write a GenerationResult — callers are responsible for logging if needed.
        """
        system_parts: list[str] = []
        turns: list[dict] = []
        for msg in messages:
            if msg["role"] == "system":
                system_parts.append(msg["content"])
            else:
                turns.append({"role": msg["role"], "content": msg["content"]})

        system_text = "\n\n".join(system_parts)
        kwargs: dict = dict(
            model=model,
            messages=turns,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        if system_text:
            kwargs["system"] = system_text

        estimated_ctx = sum(len(m.get("content", "")) for m in messages) // 4
        logger.info(
            f"[{flow_type.value}] STREAM model={model} context_tokens≈{estimated_ctx} reason={route_reason}"
        )

        async with self._client.messages.stream(**kwargs) as stream:
            async for text in stream.text_stream:
                yield text


class OpenAIProvider(AIProvider):
    """
    OpenAI implementation.

    Kept in the abstraction so Whisper-based callers can share the same
    interface if needed in the future.  Not used for text generation — all
    text generation goes through AnthropicProvider.
    """

    def __init__(self, api_key: str) -> None:
        from openai import AsyncOpenAI
        self._client = AsyncOpenAI(api_key=api_key)

    async def generate(
        self,
        messages: list[dict],
        *,
        model: str,
        flow_type: FlowType,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        route_reason: str = "",
    ) -> GenerationResult:
        start = time.monotonic()

        response = await self._client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        elapsed_ms = int((time.monotonic() - start) * 1000)
        content = response.choices[0].message.content or ""
        usage = response.usage

        logger.debug(
            f"[OpenAIProvider] flow={flow_type.value} model={model} "
            f"in={usage.prompt_tokens if usage else '?'} "
            f"out={usage.completion_tokens if usage else '?'} ms={elapsed_ms}"
        )

        return GenerationResult(
            content=content,
            model_used=model,
            provider="openai",
            flow_type=flow_type,
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=usage.completion_tokens if usage else 0,
            generation_ms=elapsed_ms,
            route_reason=route_reason,
        )
