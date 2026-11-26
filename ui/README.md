# MEHR AI STUDIO — responsive dashboard

A dependency-free responsive web dashboard prototype for the MEHR AI STUDIO control plane.

## Visual system
- Original AI-workspace interface informed by common SaaS/AI product conventions; it does not copy a single product.
- Deep navy navigation, restrained indigo/violet actions, spacious cards, clear hierarchy and subtle gradients.
- Persian RTL is the default; English LTR is available from the language control.
- Light/dark themes and responsive desktop, tablet and narrow Android layouts.
- Plain HTML, CSS and JavaScript; no frontend build tool is required.

## Preview
Open `index.html` in a browser. Or from the repository root run:

```bash
python -m http.server 8000
```

Then open `http://127.0.0.1:8000/ui/` on the same device.

## Current integration boundary

The Agent workspace includes a browser-side MCP Streamable HTTP client for the
authenticated Python service. When the OIDC resource server is deployed, the
user can enter its HTTPS `/mcp` endpoint and a short-lived access token for
that exact audience. The client initializes a session, discovers tools, reads
the caller's tenant-scoped model registry, seeds an empty tenant catalogue, and
dispatches tasks through the bounded server-side orchestrator. Tokens remain
in page memory only and are cleared on disconnect or reload.

The provider API keys remain in the Python service's server-side environment;
they are never entered into the dashboard. A registry entry is not runnable
until a supported adapter and server-side credentials are configured. A model
becomes tested only after a successful connector smoke test.

The separate single-provider Cloudflare Worker integration remains available
for the home composer and MEHR Live room. Its OIDC token is not automatically
valid for the Python MCP audience. Real project records, persistent workflow
history, progress streaming, validated file uploads, and account onboarding
remain outside the current V1 integration.

## Next integration sequence
1. Configure and verify a real OIDC resource server for the MCP endpoint.
2. Provision provider credentials through the server-side secret manager.
3. Provision provider secrets in the server environment, complete connector smoke tests, and verify bounded task execution.
4. Add workflow progress, job history, and cancellation.
5. Complete voice/camera end-to-end tests on supported Android and desktop devices.
6. Finish accessibility, quota, cost, security, and release QA.
 
## MEHR Live — Voice & Vision

The Live Room includes separate microphone and camera permission controls,
local camera preview, microphone mute, stop-all teardown, and a direct
Realtime WebRTC audio path through the Cloudflare Worker. Camera input is
consent-gated: sampled JPEG frames are sent at a bounded interval, with an
optional SFU video bridge. It is not a continuous high-frame-rate video stream.

The browser and Worker code paths are present, but live provider credentials,
OIDC/Worker configuration, and real Android/desktop end-to-end operation have
not been verified in production. See
[MEHR Live Voice & Vision Architecture](../docs/MEHR-LIVE-VOICE-VISION.md)
for the product contract and release gates.
