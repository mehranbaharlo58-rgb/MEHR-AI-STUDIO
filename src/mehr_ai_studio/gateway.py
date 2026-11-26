"""Local-first OpenAI-compatible FastAPI gateway backed by Ollama."""
from __future__ import annotations

import json
import os
import secrets
import time
import uuid
from collections import deque
from collections.abc import AsyncIterator
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from .ollama_adapter import OllamaAdapter, OllamaError


class ChatMessage(BaseModel):
    role: str = Field(pattern=r"^(system|user|assistant|tool)$")
    content: str


class ChatRequest(BaseModel):
    model: str
    messages: list[ChatMessage] = Field(min_length=1)
    temperature: float = Field(default=0.2, ge=0, le=2)
    stream: bool = False


class EmbeddingRequest(BaseModel):
    model: str
    input: str | list[str]


class WindowRateLimiter:
    """Small per-process fixed-window limiter; suitable for a local single-user gateway."""

    def __init__(self, limit: int = 60, window_s: int = 60) -> None:
        if limit < 1 or window_s < 1:
            raise ValueError("rate_limit_and_window_must_be_positive")
        self.limit, self.window_s = limit, window_s
        self._hits: dict[str, deque[float]] = {}

    def allow(self, key: str, now: float | None = None) -> bool:
        current = time.monotonic() if now is None else now
        hits = self._hits.setdefault(key, deque())
        while hits and current - hits[0] >= self.window_s:
            hits.popleft()
        if len(hits) >= self.limit:
            return False
        hits.append(current)
        return True


def create_app(
    adapter: OllamaAdapter | None = None,
    *,
    api_key: str | None = None,
    rate_limit: int = 60,
    rate_window_s: int = 60,
) -> FastAPI:
    ollama = adapter or OllamaAdapter(
        base_url=os.getenv("MEHR_OLLAMA_URL", "http://127.0.0.1:11434"),
        timeout_s=float(os.getenv("MEHR_OLLAMA_TIMEOUT", "120")),
    )
    expected_key = (api_key if api_key is not None else os.getenv("MEHR_GATEWAY_API_KEY", "")).strip()
    limiter = WindowRateLimiter(rate_limit, rate_window_s)
    app = FastAPI(title="MEHR AI Gateway", version="1.0.0")

    async def authenticate(
        request: Request,
        authorization: str | None = Header(default=None),
    ) -> None:
        if not expected_key:
            raise HTTPException(status_code=503, detail="gateway_api_key_not_configured")
        supplied = authorization[7:].strip() if authorization and authorization.startswith("Bearer ") else ""
        if not supplied or not secrets.compare_digest(supplied, expected_key):
            raise HTTPException(status_code=401, detail="invalid_api_key")
        client_host = request.client.host if request.client else "local"
        if not limiter.allow(client_host):
            raise HTTPException(status_code=429, detail="rate_limit_exceeded")

    @app.get("/health")
    async def health() -> dict[str, Any]:
        return await ollama.health()

    @app.get("/v1/models", dependencies=[Depends(authenticate)])
    async def list_models() -> dict[str, Any]:
        try:
            return {"object": "list", "data": await ollama.models()}
        except OllamaError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    @app.post("/v1/chat/completions", dependencies=[Depends(authenticate)])
    async def chat_completions(body: ChatRequest):
        messages = [message.model_dump() for message in body.messages]
        request_id = "chatcmpl-" + uuid.uuid4().hex
        created = int(time.time())
        if not body.stream:
            try:
                answer = await ollama.chat(body.model, messages, temperature=body.temperature)
            except OllamaError as exc:
                raise HTTPException(status_code=502, detail=str(exc)) from exc
            return {
                "id": request_id,
                "object": "chat.completion",
                "created": created,
                "model": body.model,
                "choices": [{"index": 0, "message": {"role": "assistant", "content": answer},
                             "finish_reason": "stop"}],
            }

        async def event_stream() -> AsyncIterator[str]:
            try:
                async for token in ollama.stream_chat(
                    body.model, messages, temperature=body.temperature
                ):
                    chunk = {
                        "id": request_id, "object": "chat.completion.chunk",
                        "created": created, "model": body.model,
                        "choices": [{"index": 0, "delta": {"content": token},
                                     "finish_reason": None}],
                    }
                    yield "data: " + json.dumps(chunk, ensure_ascii=False) + "\n\n"
                final = {
                    "id": request_id, "object": "chat.completion.chunk",
                    "created": created, "model": body.model,
                    "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                }
                yield "data: " + json.dumps(final) + "\n\n"
                yield "data: [DONE]\n\n"
            except OllamaError:
                error = {"error": {"message": "ollama_stream_failed", "type": "upstream_error"}}
                yield "data: " + json.dumps(error) + "\n\n"

        return StreamingResponse(event_stream(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    @app.post("/v1/embeddings", dependencies=[Depends(authenticate)])
    async def embeddings(body: EmbeddingRequest) -> dict[str, Any]:
        try:
            vectors = await ollama.embed(body.model, body.input)
        except OllamaError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        data = [
            {"object": "embedding", "index": index, "embedding": vector}
            for index, vector in enumerate(vectors)
        ]
        return {
            "object": "list", "data": data, "model": body.model,
            "usage": {"prompt_tokens": 0, "total_tokens": 0},
        }

    return app


app = create_app()


def main() -> None:
    """Run the local gateway; keep the listener on loopback by default."""
    import uvicorn

    host = os.getenv("MEHR_GATEWAY_HOST", "127.0.0.1")
    port = int(os.getenv("MEHR_GATEWAY_PORT", "8080"))
    if not 1 <= port <= 65535:
        raise ValueError("MEHR_GATEWAY_PORT_must_be_valid")
    uvicorn.run(app, host=host, port=port, proxy_headers=False)


if __name__ == "__main__":
    main()
