# MEHR Live API — Development Operations

Status: API implementation in development; not deployed
Branch: `feat/mehr-live-session-contracts`

## Current implementation

The Cloudflare Worker now includes:
- RS256 OIDC access-token verification against a configured HTTPS JWKS endpoint.
- Validation of issuer, audience, expiry, issued-at/not-before, subject, client identity, required scopes, and a constrained tenant claim.
- A Durable Object session registry that binds each opaque application session ID to the verified subject and tenant.
- A maximum live session lifetime of 10 minutes.
- Authenticated SFU session creation, media publication, SDP renegotiation, and media-track closure endpoints.
- Strict media request size, SDP length, track-name, MID, mode, and consent checks.
- CORS preflight support for the DELETE close operation.

This is server-side groundwork, not a complete live product. The dashboard does not yet perform OIDC Authorization Code + PKCE, call these endpoints, create a PeerConnection, or play remote media. No AI real-time speech provider is connected.

## Required runtime configuration

Set the following values in the Cloudflare Worker environment. Use the Cloudflare dashboard or Wrangler secret store; do not add credentials to Git, browser JavaScript, or issue comments.

| Variable | Purpose |
|---|---|
| `OIDC_ISSUER_URL` | Exact HTTPS issuer configured at the identity provider |
| `OIDC_JWKS_URL` | HTTPS JWKS URL for that issuer |
| `OIDC_AUDIENCE` | Audience expected in access tokens |
| `OIDC_REQUIRED_SCOPES` | Required scopes; default `studio:access` |
| `OIDC_TENANT_CLAIM` | Trusted tenant claim; default `tenant_id` |
| `CLOUDFLARE_SFU_APP_ID` | SFU application ID |
| `CLOUDFLARE_SFU_APP_SECRET` | SFU App Secret; secret storage only |

The `LIVE_SESSIONS` Durable Object binding and `v1-live-session-registry` SQLite-class migration are declared in `wrangler.jsonc`. The migration takes effect only when a deployment is performed.

## API contract

All endpoints require:
- Exact configured `Origin`
- `Authorization: Bearer <OIDC access token>`
- A valid signature and all required claims/scopes
- A verified tenant claim; user/tenant identity is never accepted from the request body

### Inspect capability readiness

`GET /api/live/capabilities`

Returns authenticated capability state. It returns HTTP 503 until SFU credentials and the Durable Object binding are present.

### Create an application session

`POST /api/live/sessions`

Voice:
```json
{
  "mode": "voice",
  "consent": { "microphone": true, "camera": false }
}
```

Voice + vision:
```json
{
  "mode": "voice_vision",
  "consent": { "microphone": true, "camera": true }
}
```

The response contains an opaque application session ID and expiry. The provider's internal session ID is not returned.

### Publish local tracks

`POST /api/live/sessions/{applicationSessionId}/publish`

Body contains the browser's gathered local SDP offer and one or two local tracks named `microphone` and optionally `camera`. The browser must request media permission only after explicit user action. Camera publication must match the session's recorded camera consent.

### Complete SFU renegotiation

`PUT /api/live/sessions/{applicationSessionId}/renegotiate`

Accepts only a bounded SDP answer and forwards it to the provider's `/sessions/{providerSessionId}/renegotiate` endpoint after verifying the session owner and tenant. CORS explicitly permits PUT. The browser must complete this exchange before mutating the same SFU session again.

### Close a session

`DELETE /api/live/sessions/{applicationSessionId}`

Only the verified owner in the same tenant can close the session. The Worker asks the SFU to force-close the recorded media tracks and then deletes the application session record.

## Security and operational limitations

- The OIDC verifier uses a five-minute in-memory JWKS cache and forces one refresh when a key is unknown or signature verification fails. Validate this behavior against the selected identity provider's key-rotation policy.
- The current session registry enforces ownership and expiry, but does not yet provide per-user concurrency quotas or distributed rate limiting.
- Session setup and SFU negotiation must be serialized per PeerConnection. The browser now handles an SFU offer marked `requiresImmediateRenegotiation` and submits its gathered answer through the authenticated renegotiation route. Concurrent mutations are not yet protected by a distributed per-session lock.
- The close route closes media tracks; it does not claim to terminate a provider-side session with a dedicated DELETE operation.
- If an SFU create succeeds but registry persistence fails, an orphaned provider session may remain until SFU resource cleanup. Add compensating cleanup and reconciliation before production.
- The publish route records only successful track MIDs returned by the SFU and exposes a `partial` flag. Validate the exact per-track response shape against live SFU responses before production.
- The browser dashboard still uses a legacy owner-token flow for the separate text-generation endpoint. Do not expose that token to untrusted users.
- No public deployment, real OIDC issuer, SFU credentials, or end-to-end browser test has been verified.

## Validation required next

1. Add broader negative tests for malformed, expired, wrong-audience, wrong-issuer, and missing-scope tokens.
2. Add deterministic SFU publish/partial-failure/close tests and verify the live response schema.
3. Add provider cleanup reconciliation and per-user concurrency/rate limits.
4. Implement browser OIDC PKCE and media publishing/remote playback.
5. Run the Durable Object migration in a non-production environment.
6. Test real browser-to-SFU audio/video on Android and desktop, including denied permissions and leave/reconnect.
7. Connect a separate realtime speech model and measure end-to-end latency.
8. Deploy only after all gates pass and the owner approves deployment.

## References

- https://developers.cloudflare.com/realtime/sfu/api/
- https://developers.cloudflare.com/realtime/sfu/get-started/connection-patterns/
- https://developers.cloudflare.com/realtime/sfu/concepts/negotiation/
- https://developers.cloudflare.com/durable-objects/
