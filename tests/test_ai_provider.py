"""Tests for AIProvider abstraction — structure, interface, and GenerationResult."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import fields

from app.ai.models import FlowType, GenerationResult
from app.ai.provider import AIProvider, AnthropicProvider, OpenAIProvider
from app.ai.router import ModelRouter


# ── GenerationResult dataclass ────────────────────────────────────────────────

class TestGenerationResult:
    def test_has_required_fields(self):
        field_names = {f.name for f in fields(GenerationResult)}
        required = {
            "content", "model_used", "provider", "flow_type",
            "prompt_tokens", "completion_tokens", "generation_ms", "route_reason",
        }
        assert required.issubset(field_names)

    def test_instantiation_with_defaults(self):
        result = GenerationResult(
            content="hello",
            model_used="claude-sonnet",
            provider="anthropic",
            flow_type=FlowType.CHAT,
        )
        assert result.content == "hello"
        assert result.prompt_tokens == 0
        assert result.completion_tokens == 0
        assert result.generation_ms == 0
        assert result.route_reason == ""


# ── FlowType enum ─────────────────────────────────────────────────────────────

class TestFlowType:
    def test_all_flows_defined(self):
        expected = {
            "EXTRACTION", "COMPLETENESS_CHECK", "CHAT", "SESSION_SUMMARY",
            "SESSION_PREP", "PATIENT_INSIGHT", "MESSAGE_DRAFT",
            "DEEP_SUMMARY", "TREATMENT_PLAN", "TWIN_PROFILE",
        }
        actual = {f.name for f in FlowType}
        assert expected == actual

    def test_flow_type_values_are_strings(self):
        for flow in FlowType:
            assert isinstance(flow.value, str)


# ── AIProvider abstract base ──────────────────────────────────────────────────

class TestAIProviderABC:
    def test_cannot_instantiate_abc_directly(self):
        with pytest.raises(TypeError):
            AIProvider()

    def test_subclass_must_implement_generate(self):
        class IncompleteProvider(AIProvider):
            pass

        with pytest.raises(TypeError):
            IncompleteProvider()


# ── AnthropicProvider — message format ───────────────────────────────────────

class TestAnthropicProviderMessageFormat:
    @pytest.fixture
    def mock_anthropic_response(self):
        mock_content = MagicMock()
        mock_content.text = "Generated response text"
        mock_usage = MagicMock()
        mock_usage.input_tokens = 100
        mock_usage.output_tokens = 50
        mock_response = MagicMock()
        mock_response.content = [mock_content]
        mock_response.usage = mock_usage
        return mock_response

    @pytest.mark.asyncio
    async def test_splits_system_from_user_messages(self, mock_anthropic_response):
        """AnthropicProvider must separate system messages from user/assistant turns."""
        captured_kwargs = {}

        async def mock_create(**kwargs):
            captured_kwargs.update(kwargs)
            return mock_anthropic_response

        with patch("anthropic.AsyncAnthropic") as mock_cls:
            mock_instance = MagicMock()
            mock_instance.messages.create = mock_create
            mock_cls.return_value = mock_instance

            provider = AnthropicProvider(api_key="test-key")
            messages = [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Hello"},
            ]
            await provider.generate(
                messages,
                model="claude-sonnet",
                flow_type=FlowType.CHAT,
            )

        assert captured_kwargs.get("system") == "You are a helpful assistant."
        turns = captured_kwargs.get("messages", [])
        assert len(turns) == 1
        assert turns[0]["role"] == "user"
        assert turns[0]["content"] == "Hello"

    @pytest.mark.asyncio
    async def test_no_system_message_no_system_kwarg(self, mock_anthropic_response):
        """If no system message, system kwarg should not be passed."""
        captured_kwargs = {}

        async def mock_create(**kwargs):
            captured_kwargs.update(kwargs)
            return mock_anthropic_response

        with patch("anthropic.AsyncAnthropic") as mock_cls:
            mock_instance = MagicMock()
            mock_instance.messages.create = mock_create
            mock_cls.return_value = mock_instance

            provider = AnthropicProvider(api_key="test-key")
            messages = [{"role": "user", "content": "Hello"}]
            await provider.generate(
                messages,
                model="claude-sonnet",
                flow_type=FlowType.CHAT,
            )

        assert "system" not in captured_kwargs

    @pytest.mark.asyncio
    async def test_returns_generation_result(self, mock_anthropic_response):
        with patch("anthropic.AsyncAnthropic") as mock_cls:
            mock_instance = MagicMock()
            mock_instance.messages.create = AsyncMock(return_value=mock_anthropic_response)
            mock_cls.return_value = mock_instance

            provider = AnthropicProvider(api_key="test-key")
            result = await provider.generate(
                [{"role": "user", "content": "Hello"}],
                model="claude-sonnet",
                flow_type=FlowType.SESSION_SUMMARY,
                route_reason="flow:session_summary,tier:standard",
            )

        assert isinstance(result, GenerationResult)
        assert result.content == "Generated response text"
        assert result.provider == "anthropic"
        assert result.model_used == "claude-sonnet"
        assert result.flow_type == FlowType.SESSION_SUMMARY
        assert result.prompt_tokens == 100
        assert result.completion_tokens == 50
        assert result.route_reason == "flow:session_summary,tier:standard"
        assert result.generation_ms >= 0

    @pytest.mark.asyncio
    async def test_multiple_system_messages_joined(self, mock_anthropic_response):
        """Multiple system messages should be joined with double newline."""
        captured_kwargs = {}

        async def mock_create(**kwargs):
            captured_kwargs.update(kwargs)
            return mock_anthropic_response

        with patch("anthropic.AsyncAnthropic") as mock_cls:
            mock_instance = MagicMock()
            mock_instance.messages.create = mock_create
            mock_cls.return_value = mock_instance

            provider = AnthropicProvider(api_key="test-key")
            messages = [
                {"role": "system", "content": "Part 1."},
                {"role": "system", "content": "Part 2."},
                {"role": "user", "content": "Hello"},
            ]
            await provider.generate(
                messages,
                model="claude-sonnet",
                flow_type=FlowType.CHAT,
            )

        assert captured_kwargs.get("system") == "Part 1.\n\nPart 2."


# ── ModelRouter integration with provider ─────────────────────────────────────

class TestRouterProviderIntegration:
    """Verify that the router's resolved model_id reaches the provider."""

    @pytest.mark.asyncio
    async def test_router_resolved_model_passed_to_provider(self):
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="ok")]
        mock_response.usage = MagicMock(input_tokens=10, output_tokens=5)

        with patch("anthropic.AsyncAnthropic") as mock_cls:
            mock_instance = MagicMock()
            call_args = {}

            async def capture_create(**kwargs):
                call_args.update(kwargs)
                return mock_response

            mock_instance.messages.create = capture_create
            mock_cls.return_value = mock_instance

            provider = AnthropicProvider(api_key="test-key")
            router = ModelRouter()

            model_id, reason = router.resolve(FlowType.SESSION_SUMMARY)
            await provider.generate(
                [{"role": "user", "content": "test"}],
                model=model_id,
                flow_type=FlowType.SESSION_SUMMARY,
                route_reason=reason,
            )

        from app.core.config import settings
        assert call_args.get("model") == settings.AI_STANDARD_MODEL
