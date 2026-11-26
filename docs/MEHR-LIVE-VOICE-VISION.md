# MEHR Live — Voice, Vision & Avatar Architecture

## Product decision

MEHR Live is a first-class interaction mode in MEHR AI STUDIO, not a microphone button attached to ordinary chat. The product target is a natural, two-way audiovisual conversation on mobile and desktop, with both the user-visible camera experience and a visible speaking agent avatar.

The complete experience must support:

- Full-duplex spoken conversation with the selected lead agent.
- The agent perceiving the user's voice and, with explicit consent, selected camera frames.
- Spoken agent responses with interruption/barge-in, live transcript, reconnect and explicit end-session controls.
- A visible animated agent avatar whose mouth movement is synchronized to generated speech, with expressive states where supported. The avatar is a required product capability, not a decorative mock or a substitute for the actual agent.
- Tool delegation from the live agent to the authenticated MEHR orchestration backend. Private provider credentials and privileged tools remain server-side.
- Session history, usage accounting, explicit consent, and user-controlled camera/microphone shutdown.

The implementation must distinguish three different capabilities: still-image understanding from sampled camera frames, continuous video understanding, and generated live avatar video. A provider supporting one does not imply support for the others. The interface must label the actual active mode and must never represent sampled images as continuous video.

## Interaction modes

1. **Voice** — microphone and spoken agent response, no camera.
2. **Voice + Vision** — voice session plus user-approved camera frames or shared images.
3. **Voice + Vision + Avatar** — the full target experience: the user can be seen/heard and the agent appears as a synchronized speaking avatar.
4. **Visual workspace** — share an image, document, screenshot or engineering drawing during a voice session.

The product may release modes incrementally, but the full target is mode 3. Until an avatar provider is configured and tested, show a clear non-avatar visual workspace rather than a fake talking head.

## Technical architecture

~~~text
Mobile / Desktop Browser
  ├─ Live Room UI (mic, speaker, camera, transcript, consent, controls)
  ├─ WebRTC peer connection (low-latency audio in/out)
  ├─ Camera frame sampler (opt-in still images; continuous video only if supported)
  └─ Avatar renderer (provider video stream or synchronized audio-driven avatar)
          │
          ├── HTTPS: authenticated session bootstrap
          ▼
MEHR Live Gateway (OIDC + tenant + quotas + policy)
  ├─ short-lived provider client credential
  ├─ session registry / usage ledger
  ├─ voice/vision provider adapter
  ├─ avatar provider adapter
  └─ private server-side control channel
          │
          ├── realtime audio / image events / avatar output
          ▼
Realtime Voice & Vision Provider  ───── Avatar Provider (when separate)
          │                                      │
          └──────── normalized session events ──┘
                           │
                           ▼
                 MEHR Agent Orchestrator
                   ├─ Router / Supervisor
                   ├─ specialist agents
                   ├─ MCP tools and connectors
                   └─ verification and final response
~~~

## Provider adapter contracts

The application must not couple the UI to one vendor's SDK or event schema.

Voice/vision adapter:
- `capabilities()`: voice input/output, image input, continuous video input, interruption, tool calling, supported transports.
- `create_session(tenant, policy, mode)`: returns only short-lived client connection material and safe session metadata.
- `attach_control_channel(session_id)`: optional server-side event/control connection.
- `close_session(session_id)`: closes the provider session and records final usage.
- `normalize_event(event)`: maps provider-specific events to MEHR's internal event contract.

Avatar adapter:
- `capabilities()`: live video output, audio-driven lip sync, emotion/expression controls, latency, resolution, transport and session limits.
- `create_avatar_session(voice_session, avatar_profile, policy)`: binds the avatar to the active agent session without exposing provider secrets.
- `synchronize(audio_timing, avatar_stream)`: maintains speech-to-mouth timing and reports drift.
- `close_avatar_session(session_id)`: terminates the stream and records usage.
- `normalize_avatar_event(event)`: maps provider events and failures into MEHR's internal event contract.

The orchestrator selects providers only when declared capabilities satisfy the requested mode. A catalogue entry is not proof of a working connector; live health must come from real smoke tests. If voice and avatar are separate providers, the gateway owns correlation IDs, timing, interruption propagation, cancellation and cleanup.

## Initial provider path

OpenAI Realtime is a candidate implementation for low-latency browser speech-to-speech over WebRTC. The secure browser pattern keeps the standard API key on the server and issues a short-lived client secret. The browser then uses WebRTC for audio and a data channel for session events.

Realtime image input can be delivered as image content in conversation events. Camera mode can therefore sample user-approved frames where supported; this is not equivalent to continuous video input. A separate avatar provider may be required for generated live video and synchronized lip movement. Do not assume that the voice provider also provides avatar output.

Model/provider availability, image and avatar support, supported regions, payment and account eligibility must be verified before enabling a live provider. Provider selection must consider latency, quality, licensing, data handling, regional availability, reliability and total per-minute cost.

## Security and privacy requirements

- HTTPS is mandatory outside local development.
- OIDC access token is verified server-side; tenant identity comes only from verified claims.
- Provider master keys never enter browser code, local storage, URLs, telemetry or logs.
- Browser receives a short-lived, narrowly scoped client secret only after authorization and quota checks.
- Microphone and camera are opt-in, visibly active, and can be stopped independently at any time.
- Camera frames are sampled only while camera mode is enabled; no background capture.
- Do not persist raw audio/video by default. Transcript retention is configurable and disclosed.
- Avatar generation must use an approved avatar profile and licensed assets; no impersonation or undisclosed synthetic identity.
- Tool calls from a live session are re-authorized by the backend against the tenant and tool policy. Destructive, financial or externally visible actions require explicit approval.
- Apply per-tenant concurrency, session-duration, usage and spend limits before public launch.
- Sanitize provider errors and redact credentials and sensitive event payloads.
- Ending a session must stop browser media tracks, provider voice sessions, avatar streams and delegated tasks according to cancellation policy.

## Release sequence

### L0 — Interaction shell
Responsive Live Room UI, device permission handling, camera preview, mute/camera toggles, connection states, transcript area and explicit end-session control. No claim of AI connectivity.

### L1 — Secure voice session
OIDC login and authorization-code + PKCE browser flow, authenticated session bootstrap, voice provider adapter, short-lived credential, WebRTC audio, interruption, reconnect and usage accounting. Live tests require a configured provider account and approved budget.

### L2 — Voice + Vision
Camera frame sampling with user consent, image-event transport, frame-rate/resolution limits, visible capture indicator, and tests for pause/stop and no-capture states.

### L3 — Agent orchestration
Private backend control channel, tenant-scoped MCP tools, supervisor routing, specialist handoffs, verified tool results, event timeline and human approval gates.

### L4 — Live avatar
Integrate and test an avatar provider adapter, speech-to-avatar synchronization, interruption and cancellation propagation, reconnect behavior, graceful fallback, avatar profile controls and per-session cost accounting. This phase is required to claim the complete Voice + Vision + Avatar product; it is not required to falsely block the earlier usable voice/vision releases.

## Acceptance gates

- Audio round-trip, interruption and reconnect verified on Android Chrome and desktop Chromium.
- Camera permission denied, revoked, paused and stopped paths tested.
- Avatar speech synchronization measured; drift, interruption, provider failure and fallback tested.
- No provider master key appears in browser bundles, requests or logs.
- Expired, wrong-audience, wrong-tenant and insufficient-scope tokens are rejected.
- Tenant A cannot read or operate Tenant B sessions or tool results.
- Per-tenant concurrency and spend limits enforced server-side.
- Session close stops media tracks, voice provider usage, avatar stream and delegated tasks.
- No "continuous live video understanding" claim until continuous video input is supported and tested end-to-end.
- No "live avatar" claim until real synchronized avatar output is demonstrated on supported mobile and desktop browsers.

## Current repository boundary

The dashboard now includes a generic OIDC Authorization Code + PKCE browser flow, an OIDC-protected Worker route that brokers direct Realtime WebRTC audio, and a consent-gated sampled-image path. The Cloudflare SFU session API and JPEG egress relay are separate transport foundations. These paths are implemented and covered by mocked Worker/UI tests, but no production identity provider, OpenAI secret, or SFU credentials are configured, and no real provider call or Android/desktop media test has been verified. Therefore this repository does not yet demonstrate a working live voice/vision session. The Python authenticated MCP server has tenant-scoped tools and an opt-in Streamable HTTP entry point; its integration with the live session orchestrator remains a separate task. The live avatar provider and paired desktop companion are not implemented. This document is an architecture and implementation baseline, not evidence of a working production call.


## Direct Realtime voice and sampled camera vision

The dashboard now has a direct one-to-one WebRTC path at `POST /api/live/realtime/calls`. The Worker validates the user's OIDC access token, keeps `OPENAI_API_KEY` server-side, sends the browser SDP offer and a server-owned session configuration to the Realtime API, and returns only the SDP answer. The browser receives model audio as a remote WebRTC track and receives Realtime events over a data channel.

The optional camera path is **sampled still-image input**, not a continuous video stream: when the user explicitly enables the camera and starts the session, the browser sends a downscaled JPEG frame approximately every three seconds over the Realtime data channel. The direct Realtime SDP route rejects video media tracks; camera images are not sent unless camera permission was granted. This sampling rate and image size are initial product defaults and still require device and cost testing.

The dashboard includes a generic Authorization Code + PKCE (S256) browser flow. Configure these Worker variables from the selected identity provider: `OIDC_AUTHORIZATION_URL`, `OIDC_TOKEN_URL`, `OIDC_CLIENT_ID`, `OIDC_REDIRECT_URI`, `OIDC_PUBLIC_SCOPES`, plus the existing issuer, JWKS URL, audience, and required scopes. The redirect URI must use the configured allowed origin. The identity provider must allow the dashboard origin for token-endpoint CORS and register the exact redirect URI. Access tokens are held in page memory; the PKCE verifier/state are temporary session-storage values and are cleared after callback exchange. The Worker additionally binds the validated token's authorized client claim to `OIDC_CLIENT_ID`.

Set `OPENAI_API_KEY` as a Cloudflare Worker secret, not as a committed variable or browser setting. `OPENAI_REALTIME_MODEL` and `OPENAI_REALTIME_VOICE` are optional Worker variables. Do not enable this route until the selected account, model access, geographic availability, payment route, and data-handling requirements have been checked.

**Not yet verified:** no production OIDC provider is configured; no OpenAI secret is installed; no live provider call has been made; no Android/desktop device test or end-to-end audio/image verification has been run. This code path is implemented and covered by mocked Worker/UI tests only. Sampled image input is not a substitute for continuous video understanding.
