# Realtime SFU Integration Gate

Status: blocked on production identity and SFU application provisioning
Branch: `feat/mehr-live-session-contracts`
Last reviewed: 2026-11-26

## Verified repository state

- `cloudflare/worker.mjs` exposes only `GET /api/health` and `POST /api/generate`.
- Both routes currently use one static `MEHR_API_TOKEN`. The browser stores this token in `sessionStorage` and sends it as a bearer credential.
- The current Worker does not validate per-user OIDC access tokens, derive a tenant from a verified identity, or maintain session ownership.
- The Live page currently obtains local camera/microphone permission and previews the camera. Its own status text confirms that no media is sent to a network endpoint.
- The Python OIDC verifier and authenticated MCP server factory exist, but the repository documentation says they do not yet expose a production HTTP listener.
- `wrangler.jsonc` does not contain an SFU App ID. No SFU App Secret is present in the repository (and none should be committed).

## Security decision: do not expose the current owner token as an end-user credential

The current static bearer token is suitable only for a tightly controlled private prototype. It is not an acceptable identity mechanism for a multi-user live product. Do not add SFU routes that accept this token from public browsers: any user who can inspect the browser session can reuse it, and the Worker cannot safely infer user, tenant, room membership, consent, or quota from it.

Before enabling live SFU routes, implement one of these trusted identity boundaries:
1. A real OIDC authorization-code flow for the browser, with PKCE, followed by Worker-side JWT verification against a configured issuer/JWKS, audience, expiry, and required scopes; or
2. A separately deployed authenticated backend that validates the OIDC token and proxies narrowly scoped SFU operations.

For either option:
- Derive subject and tenant only from verified claims; never accept them from JSON request fields.
- Authorize every operation against server-owned session membership.
- Keep the SFU App Secret in Worker secrets or another trusted secret manager.
- Use opaque application session IDs; do not let clients select arbitrary provider session IDs.
- Require explicit, separately recorded microphone and camera consent.
- Enforce session expiry, quotas, request-size limits, rate limits, and cleanup.
- Never log bearer tokens, App Secrets, SDP, ICE credentials, or media payloads.

## Cloudflare SFU API sequence (verified against current official documentation)

Base URL: `https://rtc.live.cloudflare.com/v1/apps/{appId}`

1. Backend creates a session: `POST /sessions/new`.
2. Browser creates an `RTCPeerConnection`, captures media only after user action, adds send-only transceivers, creates an SDP offer, and gathers ICE candidates.
3. Backend publishes tracks: `POST /sessions/{sessionId}/tracks/new`, forwarding the browser's offer and track mids.
4. Browser applies the SFU's SDP answer with `setRemoteDescription`.
5. Backend stores the provider session ID and publication names in server-owned session state, bound to verified user and tenant.
6. Authorized subscribers request remote tracks through their own SFU session and complete the required offer/answer renegotiation.
7. On leave, expiry, permission revocation, or disconnect timeout, close tracks and provider sessions.

Important protocol constraints:
- A session corresponds to one PeerConnection and one SDP negotiation state machine.
- Serialize mutations for a given session. Complete any required renegotiation before another mutation on that session.
- Check HTTP status, top-level errors, and per-track results; partial success must be handled explicitly.
- SFU session IDs, room names, and track names are identifiers, not authorization.
- Configure ICE/STUN/TURN and verify reachability from the actual target networks.
- DataChannels are a separate application-message transport. They do not grant operating-system access.

## Implementation order

### Gate A — identity and application provisioning
- [ ] Choose and implement the trusted OIDC boundary.
- [ ] Verify real issuer, JWKS, audience, expiry, scopes, and tenant mapping using live-issued test tokens.
- [ ] Provision a dedicated development SFU app; store App ID and App Secret outside source control.
- [ ] Add server-side per-user session registry and expiry/cleanup.

### Gate B — minimal media transport
- [ ] Add authenticated create-session, publish-tracks, renegotiate, and close-session endpoints.
- [ ] Add strict schema validation for SDP and track metadata; bound payload size.
- [ ] Add per-session negotiation serialization and idempotent cleanup.
- [ ] Add browser publishing flow and remote playback.
- [ ] Verify camera-off, mute, leave, reconnect, denied permissions, expired identity, cross-tenant access, and provider failures.

### Gate C — AI interaction
- [ ] Choose a real-time speech model/provider separately from the SFU.
- [ ] Connect the audio path using a documented adapter; do not treat a video-room connection as AI understanding.
- [ ] Measure end-to-end speech latency, interruption handling, and media loss.
- [ ] Add video frame sampling only after a model path that actually accepts and processes frames is integrated.

### Gate D — desktop companion
- [ ] Build a separately installed, explicitly paired local bridge.
- [ ] Start with user-started, read-only screen sharing.
- [ ] Add only allowlisted UI actions with visible per-action approval.
- [ ] Keep shell execution and unrestricted remote control out of scope.

## Acceptance evidence required before calling this live

- Automated security and contract tests pass.
- Two independent browser clients exchange real audio/video through the SFU.
- A denied or expired user cannot create, inspect, renegotiate, or close another user's session.
- Camera/microphone are off until explicit user action and stop immediately on leave.
- Provider sessions and tracks are closed on all terminal paths.
- Android browser testing and target-network connectivity are recorded.
- No production claim until a real deployment and end-to-end test are completed.

## Official references

- Cloudflare Connection API: https://developers.cloudflare.com/realtime/sfu/api/
- Cloudflare connection patterns: https://developers.cloudflare.com/realtime/sfu/get-started/connection-patterns/
- Sessions and tracks: https://developers.cloudflare.com/realtime/sfu/concepts/sessions-tracks/
- Negotiation lifecycle: https://developers.cloudflare.com/realtime/sfu/concepts/negotiation/
- Architecture and security boundary: https://developers.cloudflare.com/realtime/sfu/concepts/architecture/
- Experimental quickstart and deployment prerequisites: https://developers.cloudflare.com/realtime/sfu/get-started/
