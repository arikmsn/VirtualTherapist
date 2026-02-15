"""Tests for the AI agent"""

import pytest
from app.core.agent import TherapyAgent
from app.models.therapist import TherapistProfile, TherapeuticApproach


@pytest.fixture
def sample_profile():
    """Create a sample therapist profile for testing"""
    profile = TherapistProfile(
        therapeutic_approach=TherapeuticApproach.CBT,
        approach_description="CBT with focus on automatic thoughts",
        tone="supportive, direct",
        message_length_preference="short",
        common_terminology=["exercise", "automatic thoughts", "exposure"],
        language="he"
    )
    return profile


@pytest.mark.asyncio
async def test_agent_initialization():
    """Test agent initialization without profile"""
    agent = TherapyAgent()
    assert agent is not None
    assert agent.ai_provider in ["anthropic", "openai"]


@pytest.mark.asyncio
async def test_agent_with_profile(sample_profile):
    """Test agent initialization with therapist profile"""
    agent = TherapyAgent(therapist_profile=sample_profile)
    assert agent is not None
    assert agent.profile == sample_profile
    assert "CBT" in agent.system_prompt


@pytest.mark.asyncio
async def test_handle_start_command():
    """Test /start command"""
    agent = TherapyAgent()
    response = await agent.handle_command("start")
    assert response is not None
    assert "TherapyCompanion.AI" in response


@pytest.mark.asyncio
async def test_handle_unknown_command():
    """Test unknown command handling"""
    agent = TherapyAgent()
    response = await agent.handle_command("unknown_command")
    assert "לא מוכרת" in response  # "not recognized" in Hebrew


def test_system_prompt_personalization(sample_profile):
    """Test that system prompt is personalized"""
    agent = TherapyAgent(therapist_profile=sample_profile)
    prompt = agent.system_prompt

    # Check personalization elements
    assert "CBT" in prompt
    assert "supportive" in prompt or "תומך" in prompt
    assert "exercise" in prompt or "תרגיל" in prompt
