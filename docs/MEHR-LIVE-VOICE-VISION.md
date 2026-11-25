# MEHR Live — Voice & Vision Architecture

## Product decision

MEHR Live is a first-class interaction mode in MEHR AI STUDIO, not a microphone button attached to ordinary chat. The first release targets mobile and desktop browsers and supports:

- Full-duplex spoken conversation with the selected lead agent.
- Microphone and speaker controls, interruption/barge-in, live transcript, reconnect and explicit end-session controls.
- Optional camera sharing. The browser captures frames from the local camera and submits selected still images to the live session while audio remains on the real-time media channel.
- Tool delegation from the live agent to the authenticated MEHR orchestration backend. Private provider credentials and privileged tools remain server-side.
- Session history, usage accounting, explicit consent, and user-controlled camera/microphone shutdown.

The first release does **not** promise a continuously understood raw video stream or a photorealistic talking-avatar video feed. Those are separate capabilities and require a provider that explicitly supports them. The agent's first-release response is spoken audio plus a live visual workspace, transcript, status and optional generated artifacts.

## Interaction modes

1. **Voice** — microphone and spoken agent response, no camera.
2. **Voice + Vision** — voice session plus user-approved camera frames. This is the initial video-related capability.
3. **Visual workspace** — share an image, document, screenshot or engineering drawing during a voice session.
4. **Agent avatar (later)** — optional generated/live avatar output, behind a separate provider adapter and explicit cost/latency gate.

## Technical architecture

~~~text
Mobile / Desktop Browser
  ├─ Live Room UI (mic, speaker, camera, transcript, controls)
  ├─ WebRTC peer connection (audio in/out)
  └─ Camera frame sampler (opt-in still images)
          │
          ├── HTTPS: authenticated session bootstrap
          ▼
MEHR Live Gateway (OIDC + tenant + quotas + policy)
  ├─ short-lived provider client credential
  ├─ session registry / usage ledger
  └─ private server-side control channel
          │
          ├── WebRTC media plane
          ▼
Realtime Voice/Vision Provider
          │
          └── server-side events / tool delegation
                    ▼
             MEHR Agent Orchestrator
               ├─ Router / Supervisor
               ├─ specialist agents
               ├─ MCP tools and connectors
               └─ verification and final response
~~~

## Provider adapter contract

The application must not couple the UI to one vendor's SDK or event schema. Define a provider adapter with:

- `capabilities()`: voice input/output, image input, continuous video input, avatar output, interruption, tool calling.
- `create_session(tenant, policy, mode)`: returns only short-lived client connection material and safe session metadata.
- `attach_control_channel(session_id)`: optional server-side event/control connection.
- `close_session(session_id)`: closes the provider session and records final usage.
- `normalize_event(event)`: maps provider-specific events to MEHR's internal event contract.

The router must choose a provider only when its declared capabilities satisfy the requested mode. A catalogue entry is not proof of a working real-time connector; live health status must come from a real smoke test.

## Initial provider path

OpenAI Realtime is a candidate implementation for low-latency browser speech-to-speech over WebRTC. The documented secure browser pattern keeps the standard API key on the server and issues a short-lived client secret. The browser then uses WebRTC for audio and a data channel for session events.

Realtime image input is documented as an image content part in a conversation event. For camera mode, MEHR can capture user-approved frames and submit them as images; this is not equivalent to sending a continuous video stream. Model availability, image support, supported regions, payment and account eligibility must be verified before enabling a live provider.

## Security and privacy requirements

- HTTPS is mandatory outside local development.
- OIDC access token is verified server-side; tenant identity comes only from verified claims.
- Provider master keys never enter browser code, local storage, URLs, telemetry or logs.
- Browser receives a short-lived, narrowly scoped client secret only after authorization and quota checks.
- Microphone and camera are opt-in, visibly active, and can be stopped independently at any time.
- Camera frames are sampled only while camera mode is enabled; no background capture.
- Do not persist raw audio/video by default. Transcript retention is configurable and disclosed.
- Tool calls from a live session are re-authorized by the backend against the tenant and tool policy. Destructive, financial or externally visible actions require explicit approval.
- Apply per-tenant concurrency, session-duration, usage and spend limits before public launch.
- Sanitize provider errors and redact credentials and sensitive event payloads.

## Release sequence

### L0 — Interaction shell
Responsive Live Room UI, device permission handling, camera preview, mute/camera toggles, connection states, transcript area and explicit end-session control. No claim of AI connectivity.

### L1 — Secure voice session
OIDC login and authorization-code + PKCE browser flow, authenticated session bootstrap, provider adapter, short-lived credential, WebRTC audio, interruption, reconnect and usage accounting. Live tests require a configured provider account and approved budget.

### L2 — Voice + Vision
Camera frame sampling with user consent, image-event transport, frame-rate/resolution limits, visible capture indicator, and tests for pause/stop and no-capture states.

### L3 — Agent orchestration
Private backend control channel, tenant-scoped MCP tools, supervisor routing, specialist handoffs, verified tool results, event timeline and human approval gates.

### L4 — Optional avatar output
Evaluate live-avatar providers independently for latency, quality, licensing, regional availability, data handling and per-minute cost. Do not block L1-L3 on avatar generation.

## Acceptance gates

- Audio round-trip, interruption and reconnect verified on Android Chrome and desktop Chromium.
- Camera permission denied, revoked, paused and stopped paths tested.
- No provider master key appears in browser bundles, requests or logs.
- Expired, wrong-audience, wrong-tenant and insufficient-scope tokens are rejected.
- Tenant A cannot read or operate Tenant B sessions or tool results.
- Per-tenant concurrency and spend limits enforced server-side.
- Session close stops media tracks and provider usage.
- No "live video" marketing claim until continuous video input/output is supported and tested end-to-end.

## Current repository boundary

The existing static dashboard currently uses a separate single-provider Cloudflare Worker and has no OIDC browser login. The Python authenticated MCP server has tenant-scoped tools and an opt-in Streamable HTTP entry point, but it does not yet expose a Realtime session bootstrap endpoint. Therefore the repository is not yet capable of a live AI voice/video call. This architecture document is a design baseline, not evidence of a working call.
