# MEHR AI STUDIO — V1 local quick start

This guide matches the current V1 Agent Stack branch. It separates the local dashboard preview, the local Python MCP process, and the optional hosted live voice/vision services. Starting one does not imply that the others are connected.

## 1. Preview the bilingual dashboard

Requirements: Python 3.11+ (for the Python service); a modern browser for the UI preview.

From the repository root:

```bash
python -m http.server 8000
```

Open `http://127.0.0.1:8000/ui/`.

The dashboard is a static HTML/CSS/JavaScript app. It includes the bilingual workspace, the 100-entry discovery catalogue, search and filters, model/agent status counters, and the MEHR Live interface. The static preview does not require a frontend build step.

On a phone, the phone and computer must be on the same trusted Wi-Fi network to open the computer's LAN address, and the local server must be configured to listen on that interface. Do not expose the development server to the public internet.

## 2. Run the local Python MCP service

Create an isolated environment and install the project:

### macOS / Linux

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
ruff check src tests
pytest -q
python -m mehr_ai_studio.selfcheck
```

### Windows PowerShell

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
ruff check src tests
pytest -q
python -m mehr_ai_studio.selfcheck
```

Start the MCP process with:

```bash
python -m mehr_ai_studio
```

The default transport is MCP over stdio. It is intended to be launched by an MCP-compatible desktop client; it is not a standalone browser chat server. Configure that client to launch the command in the project environment.

## 3. Configure an AI provider for local generation

Set these environment variables in the private environment inherited by the MCP process:

- `AI_BASE_URL`: OpenAI-compatible API base URL, normally ending in `/v1`.
- `AI_API_KEY`: private provider credential.
- `AI_MODEL`: provider model identifier.
- `AI_TIMEOUT_SECONDS`: optional timeout (default 45 seconds).

Optional retry controls are `AI_MAX_ATTEMPTS` (1–5, default 3) and `AI_RETRY_BACKOFF_SECONDS` (0–10, default 0.5).

Without provider credentials, local storage, brief creation, and structural assessment can still be used, but external AI generation is not active. Never put credentials in the dashboard catalogue, source code, screenshots, or committed files.

## 4. Connect the Agent workspace to the authenticated registry/orchestrator

The browser-side Agent workspace supports the authenticated Python MCP service over Streamable HTTP. This is a separate service from the default local stdio process.

To use it, an operator must deploy the Python MCP HTTP service behind HTTPS and configure a real OIDC resource server. The browser requires:
- The HTTPS MCP endpoint.
- A short-lived access token whose audience and scopes match that MCP resource.
- A verified tenant claim.
- An exact CORS origin allowlist when the UI and service have different origins.

The service must have provider credentials provisioned server-side. The browser must never receive provider API keys. The 100 catalogue entries are discovery candidates, not 100 active integrations; only configured adapters with valid server-side credentials can run, and a model is marked tested only after a successful smoke test.

Do not expose the authenticated service publicly until issuer, audience, scopes, tenant isolation, TLS, secret management, rate limits, logging redaction, persistent storage, and security checks have been verified.

## 5. MEHR Live voice and vision

The UI contains microphone/camera permission controls, local camera preview, mute, stop-all teardown, WebRTC audio negotiation, and consent-gated camera frame delivery. Camera delivery uses sampled JPEG frames and an optional SFU bridge; it is not a continuous high-frame-rate video stream.

Live operation additionally requires a reachable, correctly configured Cloudflare Worker endpoint, valid OIDC login/token configuration, provider-side Realtime credentials, and supported browser/device permissions. The Python MCP endpoint and its token are not interchangeable with the Worker endpoint and token. A successful static UI load or CI build does not prove a live voice/video session.

Verify live operation only with an authorized test account and a real supported device. Confirm microphone audio in both directions, camera consent and frame receipt, disconnect behavior, and resource teardown.

## 6. Current V1 boundary

Included in the V1 foundation:
- Bilingual responsive dashboard and 100-entry discovery catalogue.
- Tenant-scoped registry and bounded orchestration contracts.
- Browser MCP client for the authenticated Python service.
- MEHR Live WebRTC audio and consent-gated camera paths in code.
- Local Python MCP service and SQLite-based single-user operation.

Not yet a verified production release:
- Real OIDC issuer/token and tenant onboarding.
- Live provider credentials and successful provider smoke tests.
- Real-device Android/desktop voice and camera end-to-end verification.
- Production deployment, cost controls/usage accounting, observability, security review, and release QA.

USB/Wi-Fi phone pairing and remote desktop mouse/keyboard control are deferred beyond V1. No production deployment or public release is implied by these local instructions.
