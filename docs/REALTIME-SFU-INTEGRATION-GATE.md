# Realtime SFU Integration Gate

Status: authenticated Worker and media-bridge foundations implemented; non-production deployment and device verification remain blocked
Branch: `feat/mehr-live-session-contracts`
Last reviewed: 2026-11-26

## Verified repository state

- `cloudflare/worker.mjs` implements Worker-side RS256 OIDC access-token verification against a configured HTTPS JWKS endpoint. It validates issuer, audience, expiry, issued-at, not-before, client identity, tenant claim, subject, and required scopes.
- The browser has an Authorization Code + PKCE (S256) flow. The access token is held in page memory; the PKCE verifier/state are temporary session-storage values.
- OIDC-protected SFU routes create application sessions, publish tracks, inspect sessions, renegotiate, and close sessions. Session ownership is derived from verified subject and tenant claims, not request JSON.
- `LIVE_SESSIONS` is declared as a Durable Object binding with a SQLite-class migration in `wrangler.jsonc`. Per-user rate limiting, session mutation locks, and server-owned session state are implemented.
- The direct Realtime voice route accepts an audio-only SDP offer, keeps the OpenAI API key server-side, and returns an SDP answer. Browser audio and Realtime events use WebRTC; this path is separate from the Cloudflare SFU.
- Camera-to-vision is implemented as consent-gated sampled JPEG frames. The SFU adapter egress bridge relays JPEG frames through a Durable Object to the browser, which forwards images to the Realtime data channel. This is sampled still-image input, not continuous video understanding.
- Viewer WebSocket authorization uses a random 256-bit, 30-second, single-use ticket delivered as a WebSocket subprotocol. The Durable Object consumes it transactionally and rejects replay and query-string-only viewer credentials.
- The Cloudflare Worker test workflow validates the Wrangler configuration/build and runs Worker/UI regression tests. Python quality checks run separately.
- The legacy dashboard text-generation path still uses its separate owner-token mechanism; it is not the identity boundary for the new live routes.
- No live OIDC issuer, OpenAI API secret, or Cloudflare SFU application credentials are configured in the repository. Secrets must be provisioned outside source control.

## Security and protocol constraints

- Derive subject and tenant only from verified claims; never accept them from JSON request fields.
- Authorize every operation against server-owned session membership.
- Keep OpenAI and SFU master secrets in Worker secrets or another trusted secret manager.
- Use opaque application session IDs; do not let clients select arbitrary provider session IDs.
- Require explicit microphone and camera consent. Camera capture must stop when the user disables it or ends the session.
- Enforce session expiry, quotas, request-size limits, rate limits, and cleanup.
- Never log bearer tokens, App Secrets, SDP, ICE credentials, or media payloads.
- Serialize mutations for a given session and handle partial provider success explicitly.
- WebRTC/DataChannels and the SFU relay do not grant operating-system access. Desktop control requires a separate paired local companion with local authorization.

## Remaining release gates

### Gate A — non-production provisioning
- [ ] Configure a real OIDC issuer, JWKS URL, audience, client ID, scopes, and exact redirect URI.
- [ ] Provision a dedicated development Cloudflare Realtime SFU application.
- [ ] Store SFU App ID and App Secret, OpenAI API key, and other credentials as Worker secrets/variables using the supported deployment process.
- [ ] Deploy to a non-production Worker and apply the declared Durable Object migration.
- [ ] Verify live-issued tokens, key rotation, expiry, wrong audience, wrong tenant, and insufficient-scope rejection.

### Gate B — real media verification
- [ ] Verify actual audio round-trip, interruption, reconnect, and session close on Android Chrome and desktop Chromium.
- [ ] Verify actual SFU JPEG adapter ingest, viewer WebSocket ticket authorization, frame delivery, and bridge shutdown.
- [ ] Verify image interpretation from sampled frames and confirm the UI labels this as sampled images, not continuous video.
- [ ] Test denied/revoked microphone and camera permissions, camera-off mode, background tab behavior, network loss, provider errors, and replayed viewer tickets.
- [ ] Verify usage accounting, quotas, cost limits, provider-side orphan-session reconciliation, and operational metrics.

### Gate C — desktop companion
- [ ] Build a separately installed, explicitly paired local bridge.
- [ ] Start with user-started, read-only screen observation using OS permission prompts.
- [ ] Add only allowlisted UI actions with visible per-action approval, heartbeat, revocation, and emergency stop.
- [ ] Keep mouse/keyboard input disabled until local safety and security tests pass. Do not add hidden capture, arbitrary shell execution, or unrestricted remote control.

## Known limitations

- The current SFU JPEG egress adapter is configured for low-rate sampled frames (approximately 1 FPS by default); it is not full-frame-rate video.
- The direct Realtime voice route rejects video SDP media tracks. Camera images are sent separately as sampled JPEG events.
- The close route closes recorded media tracks and adapters; it does not claim a provider-side session DELETE unless the provider API explicitly supports and the implementation verifies it.
- Session creation needs deployed fault-injection testing to verify compensating cleanup if provider creation succeeds but Durable Object persistence fails.
- A live avatar provider and synchronized avatar stream are not implemented.
- The paired desktop companion and approved desktop input control are not implemented.

## Acceptance evidence required before calling this live

- Automated Worker, UI, and Python quality checks pass on the exact release commit.
- A non-production deployment and Durable Object migration complete successfully.
- Real Android and desktop tests demonstrate audio, sampled-image delivery, interruption, reconnect, consent shutdown, and cleanup.
- Cross-tenant and expired-token tests pass against the deployed Worker.
- No provider master key appears in browser bundles, requests, URLs, or logs.
- No continuous-video, live-avatar, or desktop-control claim is made until that exact capability is implemented and demonstrated end-to-end.

## Official references

- Cloudflare Realtime SFU API: https://developers.cloudflare.com/realtime/sfu/api/
- Cloudflare connection patterns: https://developers.cloudflare.com/realtime/sfu/get-started/connection-patterns/
- Sessions and tracks: https://developers.cloudflare.com/realtime/sfu/concepts/sessions-tracks/
- Negotiation lifecycle: https://developers.cloudflare.com/realtime/sfu/concepts/negotiation/
- Cloudflare SFU architecture: https://developers.cloudflare.com/realtime/sfu/concepts/architecture/
