"""OpenAI-compatible gateway contract tests."""
from fastapi.testclient import TestClient

from mehr_ai_studio.gateway import create_app


class FakeOllama:
    async def health(self):
        return {"ok": True, "models": 1}

    async def models(self):
        return [{"id": "qwen2.5:7b", "object": "model", "owned_by": "ollama"}]

    async def chat(self, model, messages, temperature=0.2):
        return "پاسخ آزمایشی"

    async def stream_chat(self, model, messages, temperature=0.2):
        yield "سلام "
        yield "جهان"

    async def embed(self, model, inputs):
        count = len(inputs) if isinstance(inputs, list) else 1
        return [[0.1, 0.2] for _ in range(count)]


def test_gateway_requires_local_bearer_key():
    client = TestClient(create_app(FakeOllama(), api_key="local-secret"))
    assert client.get("/v1/models").status_code == 401
    assert client.get("/v1/models", headers={
        "Authorization": "Bearer wrong"
    }).status_code == 401


def test_gateway_models_chat_and_embeddings_contract():
    client = TestClient(create_app(FakeOllama(), api_key="local-secret"))
    headers = {"Authorization": "Bearer local-secret"}
    models = client.get("/v1/models", headers=headers)
    assert models.status_code == 200
    assert models.json()["data"][0]["id"] == "qwen2.5:7b"

    chat = client.post("/v1/chat/completions", headers=headers, json={
        "model": "qwen2.5:7b",
        "messages": [{"role": "user", "content": "سلام"}],
    })
    assert chat.status_code == 200
    assert chat.json()["choices"][0]["message"]["content"] == "پاسخ آزمایشی"

    embeddings = client.post("/v1/embeddings", headers=headers, json={
        "model": "nomic-embed-text", "input": ["one", "two"],
    })
    assert embeddings.status_code == 200
    assert len(embeddings.json()["data"]) == 2


def test_gateway_streams_openai_sse_and_done_marker():
    client = TestClient(create_app(FakeOllama(), api_key="local-secret"))
    response = client.post(
        "/v1/chat/completions",
        headers={"Authorization": "Bearer local-secret"},
        json={
            "model": "qwen2.5:7b",
            "messages": [{"role": "user", "content": "سلام"}],
            "stream": True,
        },
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert '"content": "سلام "' in response.text
    assert '"content": "جهان"' in response.text
    assert "data: [DONE]" in response.text


def test_gateway_rate_limits_authenticated_requests():
    client = TestClient(create_app(FakeOllama(), api_key="local-secret", rate_limit=1))
    headers = {"Authorization": "Bearer local-secret"}
    assert client.get("/v1/models", headers=headers).status_code == 200
    assert client.get("/v1/models", headers=headers).status_code == 429


def test_gateway_fails_closed_without_api_key_configuration():
    client = TestClient(create_app(FakeOllama(), api_key=""))
    assert client.get("/v1/models").status_code == 503
