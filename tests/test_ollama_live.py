"""Opt-in live integration tests. Set MEHR_OLLAMA_TEST_MODEL to enable."""
import asyncio
import os

import pytest

from mehr_ai_studio.ollama_adapter import OllamaAdapter

MODEL = os.getenv("MEHR_OLLAMA_TEST_MODEL")
pytestmark = pytest.mark.skipif(
    not MODEL,
    reason="set MEHR_OLLAMA_TEST_MODEL and run with -m integration",
)


def test_live_ollama_chat_and_stream():
    adapter = OllamaAdapter(
        base_url=os.getenv("MEHR_OLLAMA_URL", "http://127.0.0.1:11434"),
        timeout_s=float(os.getenv("MEHR_OLLAMA_TIMEOUT", "180")),
    )
    messages = [{"role": "user", "content": "Reply with a short greeting in Persian."}]

    async def run():
        health = await adapter.health()
        assert health["ok"] is True, "Ollama daemon is not healthy"
        models = await adapter.models()
        assert any(item["id"] == MODEL for item in models), (
            f"configured test model {MODEL!r} is not installed in Ollama"
        )
        answer = await adapter.chat(MODEL, messages, temperature=0)
        assert isinstance(answer, str) and answer.strip()
        chunks = [
            part async for part in adapter.stream_chat(
                MODEL, messages, temperature=0
            )
        ]
        assert chunks and "".join(chunks).strip()

    asyncio.run(run())
