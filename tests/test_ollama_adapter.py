"""Unit and protocol tests for the native Ollama adapter."""
import asyncio
import json

import httpx
import pytest

from mehr_ai_studio.ollama_adapter import OllamaAdapter, OllamaError


def test_ollama_chat_models_health_and_embeddings():
    def handler(request):
        path = request.url.path
        if path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": "qwen2.5:7b"}]})
        if path == "/api/chat":
            return httpx.Response(200, json={"message": {"content": "پاسخ محلی"}})
        if path == "/api/embed":
            return httpx.Response(200, json={"embeddings": [[0.1, 0.2]]})
        return httpx.Response(404)

    adapter = OllamaAdapter(transport=httpx.MockTransport(handler))
    async def run():
        assert (await adapter.health())["ok"] is True
        assert (await adapter.models())[0]["id"] == "qwen2.5:7b"
        assert await adapter.chat("qwen2.5:7b", [{"role": "user", "content": "سلام"}]) == "پاسخ محلی"
        assert await adapter.embed("nomic-embed-text", "hello") == [[0.1, 0.2]]
    asyncio.run(run())


def test_ollama_stream_decodes_ndjson_chunks():
    lines = [
        {"message": {"content": "سلام "}, "done": False},
        {"message": {"content": "جهان"}, "done": False},
        {"message": {"content": ""}, "done": True},
    ]
    body = "".join(json.dumps(line, ensure_ascii=False) + "\n" for line in lines).encode()

    def handler(request):
        assert request.url.path == "/api/chat"
        return httpx.Response(200, content=body)

    adapter = OllamaAdapter(transport=httpx.MockTransport(handler))
    async def run():
        chunks = [chunk async for chunk in adapter.stream_chat(
            "qwen2.5:7b", [{"role": "user", "content": "سلام"}]
        )]
        assert chunks == ["سلام ", "جهان"]
    asyncio.run(run())


def test_ollama_invalid_embedding_payload_is_rejected():
    def handler(_request):
        return httpx.Response(200, json={"embeddings": "not-a-vector"})
    adapter = OllamaAdapter(transport=httpx.MockTransport(handler))
    with pytest.raises(OllamaError):
        asyncio.run(adapter.embed("embed-model", "hello"))
