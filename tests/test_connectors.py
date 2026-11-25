"""Tests for safe OpenAI-compatible and local-runtime connector construction."""
import asyncio

import httpx
import pytest

from mehr_ai_studio.ai_stack import AIModel
from mehr_ai_studio.connectors import (
    ConnectorConfigurationError,
    OpenAICompatibleAdapter,
    build_adapters,
    smoke_test_adapter,
)


def model(**changes):
    data = {
        "id": "local.ollama",
        "name": "Local Ollama",
        "provider": "Ollama",
        "category": "reasoning",
        "capabilities": ["reasoning"],
        "task_tags": ["analysis"],
        "input_modalities": ["text"],
        "output_modalities": ["text"],
        "access_mode": "local_runtime",
        "availability": "local",
        "status": "configured",
        "model_id": "qwen2.5:7b",
        "endpoint": "http://localhost:11434/v1",
        "auth_required": False,
    }
    data.update(changes)
    return AIModel(**data)


def test_adapter_sends_chat_request_and_parses_response():
    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("Authorization")
        seen["payload"] = request.read().decode()
        return httpx.Response(200, json={
            "model": "qwen2.5:7b",
            "choices": [{"message": {"content": "پاسخ آزمایشی"}}],
        })

    adapter = OpenAICompatibleAdapter(
        "http://localhost:11434/v1", "qwen2.5:7b",
        transport=httpx.MockTransport(handler),
    )
    result = asyncio.run(adapter(model(), "سلام"))
    assert result["text"] == "پاسخ آزمایشی"
    assert seen["url"].endswith("/v1/chat/completions")
    assert seen["auth"] is None
    assert '"model":"qwen2.5:7b"' in seen["payload"]


def test_adapter_uses_bearer_key_when_configured():
    seen = {}

    def handler(request):
        seen["auth"] = request.headers.get("Authorization")
        return httpx.Response(200, json={
            "choices": [{"message": {"content": "ok"}}],
        })

    adapter = OpenAICompatibleAdapter(
        "https://api.example.com/v1", "model-x", "secret-test-only",
        transport=httpx.MockTransport(handler),
    )
    asyncio.run(adapter(model(), "hello"))
    assert seen["auth"] == "Bearer secret-test-only"


@pytest.mark.parametrize("endpoint", [
    "http://example.com/v1",
    "ftp://localhost/v1",
    "https://user:pass@example.com/v1",
    "https://example.com/v1?token=secret",
])
def test_rejects_unsafe_or_ambiguous_endpoint(endpoint):
    with pytest.raises(ConnectorConfigurationError):
        OpenAICompatibleAdapter(endpoint, "model-x")


def test_build_adapters_requires_auth_for_hosted_models():
    hosted = model(
        id="hosted.model", provider="Example Cloud", access_mode="openai_compatible",
        availability="freemium", endpoint="https://api.example.com/v1",
        model_id="model-x", auth_required=True,
    )
    assert build_adapters([hosted], environ={}) == {}
    adapters = build_adapters(
        [hosted], environ={"MEHR_AI_API_KEY_EXAMPLE_CLOUD": "secret"},
    )
    assert list(adapters) == ["hosted.model"]


def test_build_adapters_supports_local_runtime_without_api_key():
    local = model()
    adapters = build_adapters([local], environ={})
    assert list(adapters) == ["local.ollama"]


def test_catalog_only_entries_are_not_connected_by_adapter_factory():
    catalog = model(status="catalog_only")
    # Connector construction is independent of operational status; the execution
    # manager remains the authoritative gate that prevents catalogue-only dispatch.
    assert list(build_adapters([catalog], environ={})) == ["local.ollama"]



def test_smoke_test_adapter_returns_probe_and_latency():
    async def adapter(_model, _task):
        return {"text": "MEHR AI connector check passed."}

    result = asyncio.run(smoke_test_adapter(adapter, model(), timeout_s=1))
    assert result["response"] == "MEHR AI connector check passed."
    assert result["latency_ms"] >= 0


def test_smoke_test_adapter_enforces_timeout():
    async def adapter(_model, _task):
        await asyncio.sleep(0.05)
        return {"text": "late"}

    with pytest.raises(TimeoutError):
        asyncio.run(smoke_test_adapter(adapter, model(), timeout_s=0.001))
