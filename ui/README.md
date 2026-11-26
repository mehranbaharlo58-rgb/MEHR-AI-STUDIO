# MEHR AI STUDIO — responsive dashboard

A dependency-free responsive web dashboard prototype for the MEHR AI STUDIO control plane.

## Visual system
- Calm, warm-neutral product palette with muted green accents, restrained shadows, and clear card hierarchy.
- Persian RTL is the default; English LTR is available from the language control.
- Light/dark themes and responsive desktop, tablet, and narrow Android layouts.
- Plain HTML, CSS, and JavaScript; no frontend build tool is required.

## Preview

From the repository root:

```bash
python -m http.server 8000
```

Open `http://127.0.0.1:8000/ui/` on the same computer.

For phone preview, connect the phone and computer to the same trusted Wi-Fi network and open the computer's LAN address. Do not expose Python's development server to the public internet.

**Media permissions:** browser microphone and camera access require a secure context (HTTPS, or localhost on the same device). A phone opening the dashboard through plain HTTP on a computer's LAN address can preview the interface but cannot use the browser media APIs. Use a trusted HTTPS development host for phone media testing.

## What the static preview does and does not do

The dashboard can display and filter the curated 100-entry AI catalogue. These entries are discovery candidates only; they are not 100 live model connections. Selecting a file currently displays its filename only. File upload, parsing, and content processing are not implemented in this static preview.

The home composer is a UI shell. It does not execute an AI request without its separately configured backend. Do not enter provider API keys into browser code or static files.

## Authenticated Agent Workspace

The Agent workspace includes a browser-side MCP Streamable HTTP client for the authenticated Python service. When an OIDC resource server is deployed, the user can enter its HTTPS `/mcp` endpoint and a short-lived access token for that exact audience. The client initializes a session, discovers tools, reads the caller's tenant-scoped model registry, seeds an empty tenant catalogue, and dispatches tasks through the bounded server-side orchestrator. Tokens remain in page memory only and are cleared on disconnect or reload.

The default local Python MCP process uses stdio and is intended for an MCP-compatible desktop client; it is not the HTTP endpoint used by this browser panel. The browser panel requires the separately configured HTTPS service and a token valid for its resource audience. Do not weaken TLS or tenant authentication to make a local browser connection appear to work.

Provider API keys remain in the Python service's server-side environment; they are never entered into the dashboard. A registry entry is not runnable until a supported adapter and server-side credentials are configured. A model becomes tested only after a successful connector smoke test.

The separate Cloudflare Worker integration serves the home composer and MEHR Live room. Its OIDC token is not automatically valid for the Python MCP audience. Real project records, persistent workflow history, progress streaming, validated file uploads, and account onboarding remain outside the current V1 integration.

## MEHR Live — Voice & Vision

The Live Room includes separate microphone and camera permission controls, local camera preview, microphone mute, stop-all teardown, and a direct Realtime WebRTC audio path through the Cloudflare Worker. Camera input is consent-gated: sampled JPEG frames are sent at a bounded interval, with an optional SFU video bridge. It is not a continuous high-frame-rate video stream.

The browser and Worker code paths are present, but live provider credentials, OIDC/Worker configuration, and real Android/desktop end-to-end operation have not been verified in production. See [MEHR Live Voice & Vision Architecture](../docs/MEHR-LIVE-VOICE-VISION.md) for the product contract and release gates.

## Next integration sequence
1. Configure and verify a real OIDC resource server for the MCP endpoint.
2. Provision provider credentials through the server-side secret manager.
3. Complete connector smoke tests and verify bounded task execution.
4. Add workflow progress, job history, and cancellation.
5. Complete voice/camera end-to-end tests on supported Android and desktop devices.
6. Finish accessibility, quota, cost, security, and release QA.
