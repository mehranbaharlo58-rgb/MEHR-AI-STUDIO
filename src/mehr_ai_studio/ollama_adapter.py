"""Ollama native API adapter used by the OpenAI-compatible MEHR gateway."""
from __future__ import annotations

import json
from collections.abc import AsyncIterator, Sequence
from typing import Any

import httpx


class OllamaError(RuntimeError):
    """Sanitized Ollama transport or response error."""


class OllamaAdapter:
    def __init__(
        self,
        base_url: str = "http://127.0.0.1:11434",
        timeout_s: float = 120.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if timeout_s <= 0:
            raise ValueError("timeout_s_must_be_positive")
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s
        self.transport = transport

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout_s,
            transport=self.transport,
        )

    async def health(self) -> dict[str, Any]:
        try:
            async with self._client() as client:
                response = await client.get("/api/tags")
                response.raise_for_status()
                payload = response.json()
            return {"ok": True, "models": len(payload.get("models", []))}
        except (httpx.HTTPError, ValueError, TypeError):
            return {"ok": False, "error": "ollama_unavailable"}

    async def models(self) -> list[dict[str, str]]:
        try:
            async with self._client() as client:
                response = await client.get("/api/tags")
                response.raise_for_status()
                payload = response.json()
            return [
                {"id": item["name"], "object": "model", "owned_by": "ollama"}
                for item in payload.get("models", [])
                if isinstance(item, dict) and isinstance(item.get("name"), str)
            ]
        except (httpx.HTTPError, ValueError, TypeError, KeyError) as exc:
            raise OllamaError("ollama_model_list_failed") from exc

    async def chat(
        self,
        model: str,
        messages: Sequence[dict[str, Any]],
        *,
        temperature: float = 0.2,
    ) -> str:
        try:
            async with self._client() as client:
                response = await client.post(
                    "/api/chat",
                    json={
                        "model": model,
                        "messages": list(messages),
                        "stream": False,
                        "options": {"temperature": temperature},
                    },
                )
                response.raise_for_status()
                payload = response.json()
            content = payload.get("message", {}).get("content")
            if not isinstance(content, str):
                raise OllamaError("ollama_chat_response_invalid")
            return content
        except httpx.HTTPError as exc:
            raise OllamaError("ollama_chat_request_failed") from exc

    async def stream_chat(
        self,
        model: str,
        messages: Sequence[dict[str, Any]],
        *,
        temperature: float = 0.2,
    ) -> AsyncIterator[str]:
        try:
            async with self._client() as client, client.stream(
                "POST",
                "/api/chat",
                json={
                    "model": model,
                    "messages": list(messages),
                    "stream": True,
                    "options": {"temperature": temperature},
                },
            ) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        try:
                            item = json.loads(line)
                        except json.JSONDecodeError as exc:
                            raise OllamaError("ollama_stream_chunk_invalid") from exc
                        content = item.get("message", {}).get("content", "")
                        if content:
                            if not isinstance(content, str):
                                raise OllamaError("ollama_stream_content_invalid")
                            yield content
        except httpx.HTTPError as exc:
            raise OllamaError("ollama_stream_request_failed") from exc

    async def embed(self, model: str, inputs: str | list[str]) -> list[list[float]]:
        try:
            async with self._client() as client:
                response = await client.post(
                    "/api/embed",
                    json={"model": model, "input": inputs},
                )
                response.raise_for_status()
                payload = response.json()
            vectors = payload.get("embeddings")
            if not isinstance(vectors, list) or not all(
                isinstance(vector, list) and all(isinstance(value, (int, float)) for value in vector)
                for vector in vectors
            ):
                raise OllamaError("ollama_embedding_response_invalid")
            return vectors
        except httpx.HTTPError as exc:
            raise OllamaError("ollama_embedding_request_failed") from exc
