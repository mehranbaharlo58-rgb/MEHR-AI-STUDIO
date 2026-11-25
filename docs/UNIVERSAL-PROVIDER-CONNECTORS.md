# Universal provider connector increment

## Scope

This increment adds one real connector protocol: OpenAI-compatible chat completions. It can target hosted HTTPS endpoints and local loopback runtimes such as Ollama when they expose the compatible endpoint. It does not claim that every catalogue item is connected.

## Configuration

For a model record, set:
- `access_mode`: `openai_compatible` or `local_runtime`
- `endpoint`: provider base URL (for example, `https://provider.example/v1` or `http://localhost:11434/v1`)
- `model_id`: exact provider-side model identifier
- `auth_required`: true for hosted providers, false only for a trusted local runtime

Hosted credentials are read from environment variables named `MEHR_AI_API_KEY_<PROVIDER>`, where provider characters outside A-Z and 0-9 become underscores. The existing `AI_API_KEY` is used only as a fallback when the model uses the configured `AI_BASE_URL`. Secrets are never stored in the AI registry.

## Execution

The MCP tool `execute_ai_task`:
1. Matches the task against operational registry entries.
2. Builds adapters only for supported access modes with endpoint, model ID, and required credentials.
3. Dispatches at most three matched models by default, with the global/provider/model limits and timeout enforced by the execution manager.
4. Returns results and explicitly lists matched entries skipped for missing connector configuration.

It does not broadcast to all 100 catalogue entries, retry potentially billable requests, or trigger publication or other irreversible actions.

## Endpoint safety

HTTPS is required for remote providers. Plain HTTP is accepted only for loopback hosts (`localhost`, `127.0.0.1`, `::1`) to support local runtimes. URLs containing user information, query strings, or fragments are rejected. The registry is an operator-controlled configuration surface; do not allow untrusted users to register arbitrary endpoints.

## Verification boundary

Automated tests use an in-memory HTTP mock and verify request shape, response parsing, auth injection, local unauthenticated use, and endpoint rejection. These tests do not prove connectivity to any real provider. An entry must remain `configured` until a real smoke test succeeds, then may be marked `tested` with recorded evidence.
