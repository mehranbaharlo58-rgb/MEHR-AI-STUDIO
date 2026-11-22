"""Opt-in live integration test for an OpenAI-compatible provider.

Run with AI_BASE_URL, AI_API_KEY, and AI_MODEL configured in the environment.
This test sends only a harmless fixed smoke-test prompt to the configured provider.
"""
import pytest

from mehr_ai_studio.config import settings
from mehr_ai_studio.provider import generate_text

CONFIGURED = bool(
    settings.provider_base_url
    and settings.provider_api_key
    and settings.provider_model
)


@pytest.mark.skipif(
    not CONFIGURED,
    reason="Set AI_BASE_URL, AI_API_KEY, and AI_MODEL to run the live provider test",
)
def test_live_provider_returns_nonempty_text():
    result = generate_text(
        "Reply with exactly: MEHR AI STUDIO connection successful.",
        "You are running a connectivity smoke test. Follow the requested output exactly.",
    )
    assert isinstance(result["text"], str)
    assert result["text"].strip()
    assert isinstance(result["model"], str)
    assert result["model"].strip()
