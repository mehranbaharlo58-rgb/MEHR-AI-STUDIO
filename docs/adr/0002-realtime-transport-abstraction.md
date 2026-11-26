# ADR-0002: Provider-neutral realtime transport with Cloudflare SFU pilot

- Status: Proposed for implementation
- Date: 2026-11-26
- Decision owner: MEHR AI STUDIO project owner

## Context

MEHR AI STUDIO already has a Cloudflare Worker (cloudflare/worker.mjs) and a Cloudflare deployment configuration (wrangler.jsonc). The Python package has provider-neutral live-session contracts and a server-side LiveKit token issuer, but it does not yet expose an authenticated session-creation API or connect the browser UI to live media.

The product requirement is broader than a video meeting: the user must be able to share microphone/camera media with an AI agent, receive responses, and later send authorized desktop-control events through a separate local device bridge. Media transport, AI inference, and local device control must remain separate trust boundaries.

## Decision

Pilot Cloudflare Realtime SFU as the first transport adapter, while retaining LiveKit as a supported alternative behind a provider-neutral interface.

Reasons:
- The existing Cloudflare Worker can own signaling and session authorization without adding a second public backend.
- Realtime SFU supports browser WebRTC media and DataChannels. DataChannels can carry bounded, authenticated application events for a future local desktop bridge.
- Cloudflare documents a 1,000 GB monthly shared SFU/TURN egress allowance, then $0.05/GB. Confirm account-specific availability and terms before relying on it.
- LiveKit remains the fallback when its agent framework, media routing, or deployment model proves better in integration tests.
- Daily Video SDK is a rapid UI/integration alternative with 10,000 free participant minutes/month, but is not selected as the primary custom-control transport.
- Cloudflare RealtimeKit is the quickest managed meeting UI option; evaluate it separately if custom SFU signaling becomes the dominant delivery risk.

## Target boundaries

1. Browser UI: requests explicit microphone/camera permission and captures media only after user action.
2. Authenticated application backend: validates the user's OIDC identity, tenant, session consent, quotas, and allowed operation.
3. Transport adapter: creates SFU sessions, exchanges SDP, publishes/subscribes tracks, and closes sessions. App secrets stay server-side.
4. AI runtime: consumes permitted audio/video inputs and returns audio/text outputs through a replaceable model adapter. The transport provider is not the AI brain.
5. Local desktop bridge: an independently installed, explicitly paired local agent. It accepts only allowlisted actions after visible user approval. Browser media or DataChannel connectivity alone never grants operating-system control.
6. Audit/limits: record session IDs, state transitions, consent, quota use, and safe error codes; never log secrets, bearer tokens, SDP, ICE credentials, or media payloads.

## Provider interface

Implement a narrow asynchronous interface with:
- capabilities()
- create_session(principal, consent, limits)
- publish_tracks(session, offer)
- subscribe_tracks(session, publications)
- send_control_event(session, event)
- close_session(session)

Provider-specific credentials and identifiers must not leak into public API responses. The application owns authorization and stable session IDs; provider session IDs are internal.

## Rollout sequence

1. Add provider interface and contract tests without changing the current default app.
2. Implement Cloudflare SFU adapter in the existing Worker, using the Realtime Connection API. Authenticate every endpoint and validate room membership before each provider call.
3. Implement a browser two-party media proof: microphone and camera publish, remote playback, mute/camera-off, leave, reconnect, and denied-permission cases.
4. Add audio adapter to a selected realtime speech model; verify round-trip latency and interruption behavior independently of video.
5. Add bounded video-frame sampling and explicit per-session camera consent.
6. Implement local desktop bridge as a separate opt-in component. Start with read-only screen observation; add allowlisted mouse/keyboard actions only after pairing and per-action confirmation.
7. Run security, browser, Android, network, and provider-failure tests. Keep LiveKit adapter as fallback and compare measured reliability/cost.
8. Enable production only after secrets, quotas, abuse controls, data retention, and deployment checks are verified.

## Explicit non-goals

- No claim of continuous video understanding until the model path actually accepts and processes live frames.
- No claim of desktop control from a browser-only session.
- No automatic control of a user's computer, arbitrary shell execution, credential capture, or hidden recording.
- No provider lock-in and no client-side provider secrets.

## Risks and gates

- Cloudflare Realtime SFU examples are marked experimental; validate API stability and account eligibility before committing production traffic.
- Cloudflare's free allowance and pricing can change. Enforce application-level usage quotas and spend alarms.
- Network reachability and service availability from the user's actual location are unverified. Test from target networks; do not assume a VPN or policy bypass.
- OIDC issuer, tenant mapping, CORS, TLS, rate limiting, and secret storage remain deployment prerequisites.
- LiveKit and Daily accounts, payment methods, regional availability, and service terms must be verified before treating them as usable fallbacks.

## Acceptance criteria

- Automated contract tests pass for all provider adapters.
- Browser-to-browser microphone/camera test passes on supported desktop and Android browsers.
- Unauthorized, cross-tenant, expired, over-quota, and unconsented requests fail closed.
- A session can be closed and all media tracks stop.
- Audio AI response and interruption are measured end-to-end.
- Desktop bridge cannot execute unpaired or unapproved commands.
- Provider switching does not require changes to UI session contracts.
