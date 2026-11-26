# MEHR Live API — Development Operations

Status: implemented in branch; not deployed
Branch: feat/mehr-live-session-contracts

## Current implementation

The Cloudflare Worker includes:
- RS256 OIDC access-token verification against a configured HTTPS JWKS endpoint, including issuer, audience, expiry, iat/nbf, subject, client identity, scopes, and tenant validation.
- Public-client OIDC Authorization Code + PKCE flow in the browser UI, including state and nonce handling.
- Durable Object application-session registry binding opaque session IDs to verified subject and tenant, with a maximum ten-minute lifetime.
- Cloudflare Realtime SFU session creation, track publication, inspection, renegotiation, and close operations.
- Direct Realtime WebRTC call initialization through the Worker; the standard API key remains server-side.
- Browser WebRTC media handling, remote audio playback, data-channel event handling, transcript UI, and consent-gated sampled still-image input.
- Per-user action quotas and atomic Durable Object counters.
- Owner/tenant-scoped, expiring Durable Object mutation locks around SFU publish, renegotiation, and close.
- Request-size, SDP, track-name, MID, mode, and consent validation.

This is not a production-verified live AI product. Automated tests verify application logic and request construction, not successful upstream connectivity, media quality, image understanding, or Android/desktop compatibility. The Cloudflare SFU transport is a separate multi-track option; the direct Realtime connection is the intended voice-agent path.

## Required runtime configuration

Set runtime configuration in the Cloudflare Worker environment or secret store. Never commit credentials or place standard API keys in browser JavaScript.

| Variable | Purpose |
|---|---|
| OIDC_ISSUER_URL | Exact HTTPS issuer |
| OIDC_JWKS_URL | HTTPS JWKS endpoint |
| OIDC_AUDIENCE | Expected access-token audience |
| OIDC_REQUIRED_SCOPES | Required scopes; default studio:access |
| OIDC_TENANT_CLAIM | Trusted tenant claim; default tenant_id |
| OIDC_CLIENT_ID | Expected public client identifier, when configured |
| OPENAI_API_KEY | Server-only Realtime API key |
| OPENAI_REALTIME_MODEL | Server-selected Realtime model |
| CLOUDFLARE_SFU_APP_ID | SFU application ID |
| CLOUDFLARE_SFU_APP_SECRET | SFU App Secret; secret storage only |

The LIVE_SESSIONS Durable Object binding and v1-live-session-registry SQLite-class migration are declared in wrangler.jsonc. The migration takes effect only after deployment.

## API contract

All protected endpoints require the configured Origin and a valid OIDC access token. Identity and tenant are derived from the verified token, never trusted from request JSON.

- GET /api/live/capabilities — authenticated capability readiness.
- POST /api/live/sessions — create an opaque application session with explicit microphone/camera consent.
- POST /api/live/sessions/{applicationSessionId}/publish — publish local SFU tracks using a bounded SDP offer.
- GET /api/live/sessions/{applicationSessionId} — return sanitized provider track state; active does not prove media packets are arriving.
- PUT /api/live/sessions/{applicationSessionId}/renegotiate — submit a bounded SDP answer for the owned SFU session.
- DELETE /api/live/sessions/{applicationSessionId} — close recorded tracks and delete the application session record only after closure checks.
- POST /api/live/realtime/calls — establish direct Realtime WebRTC from a browser SDP offer. The Worker forwards the offer and server-selected session configuration using the server-side API key.

The browser OIDC client uses Authorization Code + PKCE. Realtime audio travels over WebRTC; session events and transcripts use the data channel. Camera input is sampled still images with explicit consent, not continuous video understanding.

## Quotas and mutation serialization

Fixed-window quotas are scoped by verified tenant and subject:
- Session creation: 3 per 10 minutes.
- Direct Realtime initialization: 5 per 10 minutes.
- SFU track publication: 12 per minute.
- SFU renegotiation: 20 per minute.
- Session inspection: 60 per minute.
- Session close: 5 per 10 minutes.

The Durable Object uses atomic storage transactions for quota counters. SFU publish, renegotiation, and close operations acquire an owner-scoped 30-second mutation lock. Provider HTTP requests have a 15-second timeout. Competing mutations receive HTTP 409; lock release is attempted in a finally path, and expired locks can be replaced.

## Remaining production gates

1. Configure a test OIDC issuer and Worker secrets in a non-production environment.
2. Apply the Durable Object migration in that environment.
3. Test actual Realtime WebRTC audio, remote playback, transcripts, image input, graceful close, and usage accounting.
4. Test the Cloudflare SFU multi-track path, partial publication, renegotiation, close, lock expiry, and concurrent mutation rejection.
5. Test on Android and desktop browsers, including denied permissions, reconnect, network interruption, and media packet verification.
6. Add provider-side orphan-session reconciliation, metrics, and cost controls.
7. Implement the paired desktop bridge with visible status, explicit opt-in, allowlisted operations, and per-action approval.
8. Deploy only after the above gates pass and the owner explicitly approves deployment.

No production deployment, real provider credential, or live end-to-end device test is claimed by this document.

## Browser media lifecycle hardening

The Live Room browser now:
- Starts or stops camera sampling independently of the active voice connection. Stopping the camera no longer tears down an otherwise healthy audio call.
- Starts sampling when the camera is enabled either before connecting or during an established voice call.
- Sends bounded JPEG still frames at a three-second interval, capped at 640 pixels on the longest edge, with low image detail.
- Pauses frame transmission while the page is hidden and skips frames when the Realtime data channel is congested.
- Prevents duplicate concurrent Realtime calls, handles remote-audio autoplay rejection with a visible status message, and clears the session/UI state after terminal WebRTC failure.
- Stops local media tracks and the sampling timer when the user ends the session or leaves the Live Room.

These are browser-side lifecycle safeguards, not proof of live provider media quality. The current Realtime vision path remains sampled still images; it is not a continuous video stream.

## Continuous video path — not yet implemented

The next video milestone is a separate media pipeline:
1. Browser publishes a consented camera MediaStreamTrack to a Cloudflare Realtime SFU session.
2. An authenticated server-side media adapter receives the SFU video publication as JPEG frames.
3. A server-side frame gate enforces per-session authorization, sampling rate, resolution, byte limits, and backpressure.
4. The gateway forwards approved frames to the active vision conversation as image inputs, correlating them with the same user/session and audio conversation.
5. Session shutdown revokes the adapter, closes SFU tracks, stops camera capture, and records final usage.

Cloudflare documents WebRTC media forwarding and a WebSocket adapter for video egress as JPEG frames. The MEHR SFU API foundation exists, but this browser publisher → JPEG adapter → vision-session bridge is not yet wired or live-tested. Do not describe the product as continuous-video AI until that pipeline passes end-to-end tests.
