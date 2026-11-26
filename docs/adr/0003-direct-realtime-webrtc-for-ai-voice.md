# ADR-0003: Direct Realtime WebRTC for the primary AI voice path

- Status: Proposed; provider access and target-region eligibility remain unverified
- Date: 2026-11-26
- Decision owner: MEHR AI STUDIO project owner

## Context

The Cloudflare Realtime SFU pilot currently proves the media-transport boundary and provides an authenticated browser-to-SFU publication path. It does not perform speech recognition, generate speech, understand images, or provide an AI agent. Routing browser media through an SFU and then adding a separate voice provider can create unnecessary hops for a one-user voice conversation.

The product requires low-latency, two-way speech, explicit camera sharing, and later delegation to MEHR tools. It must not confuse still-frame vision with continuous video understanding.

## Decision

Use a provider-neutral voice adapter contract, with OpenAI Realtime WebRTC as the first candidate adapter for direct browser-to-agent audio. Prefer the unified server-mediated WebRTC connection flow where the Worker exchanges the browser SDP offer with the provider using a server-held API key. Do not expose the standard API key to the browser. An ephemeral client-secret flow is an alternative only when its security, usage, and lifecycle requirements are explicitly met.

Retain Cloudflare Realtime SFU as a separate optional transport for multi-device relay, browser-to-browser media, and future desktop/phone sessions. Do not force every single-user voice session through the SFU unless a measured product requirement needs it.

## Vision boundary

- Realtime image input may be delivered as user-approved still frames in conversation events over the negotiated data channel.
- The UI must label this as sampled-frame vision, not continuous video understanding.
- Frame sampling is user initiated or visibly enabled, rate- and resolution-limited, and stops immediately when camera sharing is disabled.
- No raw frames are stored by default.
- A future provider with true continuous video input may be added behind the same capability contract after a live integration test.

## Browser and server flow

1. User explicitly starts a voice session and grants microphone permission.
2. Browser creates an RTCPeerConnection and the required event data channel before creating the offer.
3. Browser sends the gathered SDP offer to the authenticated MEHR Worker.
4. Worker validates identity, tenant, consent, request size, quotas, and configured provider availability.
5. Worker forwards the SDP and server-owned session configuration to the selected Realtime provider using a secret held only in Worker secrets.
6. Worker returns the SDP answer; browser applies it and waits for a connected state and the provider's session-ready event.
7. Browser sends user-approved image frames as bounded input-image conversation events when vision mode is active.
8. The provider returns audio and structured events; the UI renders remote audio, transcript, interruption state, and connection status.
9. Tool calls are delegated to the MEHR backend, re-authorized per tenant and tool, and audited. Destructive or externally visible actions require explicit user approval.
10. End-session handling waits for the provider's close acknowledgement where supported, stops local tracks, clears event handlers, and records usage state without logging secrets or media.

## Security and cost controls

- API master keys remain in Worker secrets and never enter browser code, HTML, local/session storage, URLs, or logs.
- Enforce per-user and per-tenant concurrency, session-duration, and spend limits before minting or connecting a session.
- Use a stable privacy-preserving safety identifier where the provider supports it; never send raw personal identifiers unless required and approved.
- Restrict CORS to the production UI origin and authenticate every session bootstrap.
- Do not log SDP, ICE credentials, bearer tokens, ephemeral secrets, or image/audio payloads.
- Verify provider availability, account eligibility, payment method, supported region, and data-handling terms before deployment. No assumption is made that the service is accessible from Iran or any particular network.
- Do not deploy or enable billable traffic without explicit owner approval.

## Acceptance gates

- Browser-to-provider audio round trip verified on Android Chrome and desktop Chromium.
- Session-ready event, transcript, remote audio playback, interruption, and graceful close verified.
- Camera-off and permission-revoked states stop all frame capture and transmission.
- Still-image input is verified with explicit UI labeling; no continuous-video claim is made.
- Provider keys are absent from the browser bundle and client responses.
- OIDC, tenant isolation, quota, consent, request-size, and close-path tests pass.
- Provider account access, regional availability, and cost are verified before any production enablement.

## References

- https://developers.openai.com/api/docs/guides/voice-webrtc
- https://developers.openai.com/api/docs/guides/realtime-conversations
- https://developers.cloudflare.com/realtime/sfu/api/
- https://developers.cloudflare.com/realtime/sfu/get-started/connection-patterns/
