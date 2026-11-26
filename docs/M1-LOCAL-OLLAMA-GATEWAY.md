# M1 — Local Ollama Gateway

M1 adds a local-first OpenAI-compatible HTTP gateway backed by Ollama. It does not require a hosted AI API or international payment card.

## Components and evidence status

| Component | Status | Evidence |
|---|---|---|
| Native Ollama adapter: chat/models/embeddings/health | IMPLEMENTED | `tests/test_ollama_adapter.py` |
| Ollama NDJSON to token iterator | IMPLEMENTED | `tests/test_ollama_adapter.py` |
| FastAPI OpenAI-compatible routes | IMPLEMENTED | `tests/test_gateway.py` |
| Bearer API-key authentication | IMPLEMENTED | `tests/test_gateway.py` |
| In-process rate limit | IMPLEMENTED | `tests/test_gateway.py` |
| Live Ollama chat integration | BLOCKED until a local Ollama daemon and model are available | Not run in GitHub-hosted source editing |
| Live Ollama streaming integration | BLOCKED until a local Ollama daemon and model are available | Not run in GitHub-hosted source editing |
| Production deployment | NOT_IMPLEMENTED | Out of M1 scope |

## Run locally

1. Install Ollama using its official installation method for your operating system.
2. Start the Ollama service and download a local model, for example:

```bash
ollama pull qwen2.5:3b
```

3. From the repository root, install the project and configure the local gateway key:

```bash
python -m pip install -e .
export MEHR_GATEWAY_API_KEY='replace-with-a-long-random-local-secret'
export MEHR_OLLAMA_URL='http://127.0.0.1:11434'
export MEHR_GATEWAY_HOST='127.0.0.1'
export MEHR_GATEWAY_PORT='8080'
mehr-ai-gateway
```

The gateway binds to loopback by default. Do not expose it to a LAN or public network without adding TLS, access controls, and an explicit deployment review.

## Verify the live service

Models:

```bash
curl -sS http://127.0.0.1:8080/v1/models \
  -H "Authorization: Bearer $MEHR_GATEWAY_API_KEY"
```

Non-streaming chat:

```bash
curl -sS http://127.0.0.1:8080/v1/chat/completions \
  -H "Authorization: Bearer $MEHR_GATEWAY_API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{"model":"qwen2.5:3b","messages":[{"role":"user","content":"سلام، خودت را معرفی کن."}]}'
```

Streaming chat (keep `-N` to disable curl buffering):

```bash
curl -N http://127.0.0.1:8080/v1/chat/completions \
  -H "Authorization: Bearer $MEHR_GATEWAY_API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{"model":"qwen2.5:3b","stream":true,"messages":[{"role":"user","content":"یک جمله فارسی بگو."}]}'
```

Embeddings:

```bash
curl -sS http://127.0.0.1:8080/v1/embeddings \
  -H "Authorization: Bearer $MEHR_GATEWAY_API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{"model":"nomic-embed-text","input":"MEHR AI local embeddings"}'
```

## Opt-in live integration test

The repository includes `tests/test_ollama_live.py`. It is skipped unless a model name is explicitly supplied. With Ollama running and the model already downloaded, run:

```bash
export MEHR_OLLAMA_URL='http://127.0.0.1:11434'
export MEHR_OLLAMA_TEST_MODEL='qwen2.5:3b'
pytest -q -m integration tests/test_ollama_live.py
```

This test calls the actual Ollama daemon for health, model discovery, non-streaming chat, and streaming chat. A passing run is the evidence required before marking live chat/stream as TESTED. CI without a local Ollama daemon cannot provide this evidence and will skip the opt-in test.

## Tests

Run the repository suite:

```bash
python -m pip install -e '.[dev]'
pytest -q
```

The committed adapter and gateway tests use deterministic HTTP transports and a fake adapter. They verify protocol translation, auth, rate limiting, JSON responses, and SSE framing. These tests do **not** prove that an Ollama daemon or a downloaded model is available.

A live integration check must be run on a machine with Ollama running and the selected models already pulled. Record the exact command output before marking the connector TESTED or VERIFIED.
