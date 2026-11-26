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


## Explicit connector verification

The MCP tool `test_ai_connector(model_id)` performs one small live request to the selected configured connector. A successful response records `status=tested`, `verification_status=integration_tested`, latency, and an ISO verification timestamp. A failed live probe marks the connector `degraded` without exposing provider response bodies or credentials. Catalogue-only entries cannot be probed. This tool is not called automatically: an operator should invoke it only after deciding that a real provider request is acceptable; hosted providers may charge for the request.
## OmniRoute gateway integration

OmniRoute can be used as an upstream OpenAI-compatible gateway without adding a new provider SDK. The existing `provider.py` adapter already accepts a configurable base URL, API key, and model ID.

For an OmniRoute instance reachable by the MEHR AI backend, configure these server-side environment variables:

```dotenv
AI_BASE_URL=https://<your-omniroute-host>/v1
AI_API_KEY=<your-mehr-scoped-omniroute-api-key>
AI_MODEL=auto
```

Use `AI_MODEL=auto` for OmniRoute's balanced Auto-Combo routing. If the operator explicitly wants to avoid billed fallback, use `AI_MODEL=auto/subscription`; this route can return HTTP 503 when no eligible subscription quota is available. Do not use `auto/thrifty` for a zero-spend policy because it may reach billed models. Exact model IDs or named OmniRoute combos may be used instead of `auto` when deterministic routing is required.

The OmniRoute API key is distinct from upstream provider credentials. Configure provider accounts and their permitted quotas inside the trusted OmniRoute instance, then issue a separate, least-privilege MEHR API key. Never expose either key to browser JavaScript, commit them to the repository, or place them in the public UI. Remote OmniRoute endpoints must use HTTPS and must be operator-controlled; do not accept arbitrary gateway URLs from untrusted tenants.

This integration is configuration-compatible, not a live connection claim. A real `test_ai_connector(model_id)` probe must succeed before the registry marks the connector as tested. Confirm the selected routing policy and provider terms before sending real prompts; OmniRoute's free-tier totals are aggregated across separately eligible provider accounts and are not credits granted by OmniRoute.
