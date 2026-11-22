# ADR-0001: Authentication boundary for multi-user MCP deployment

- Status: Accepted
- Date: 2026-11-22
- Decision owners: MEHR AI STUDIO maintainers

## Context

The current server starts with `FastMCP` over `stdio`. The SQLite store supports tenant-scoped rows, but the exposed MCP tools do not receive an authenticated principal and currently use the default tenant. A caller-supplied tenant identifier would be untrusted input and must not be treated as authorization.

The MCP Python SDK documents OAuth bearer-token verification for Streamable HTTP through a `TokenVerifier`, `AuthSettings`, and request-scoped `get_access_token()`. Its authorization middleware does not protect `stdio`; the process boundary is the security boundary for that transport.

## Decision

1. Keep `stdio` as the only enabled/default transport for the current single-user local product.
2. Do not expose a network transport or claim multi-user security until a real authorization-server integration is configured and tested.
3. For a future HTTP deployment, use Streamable HTTP with an external OAuth 2.1 authorization server and an SDK `TokenVerifier`. The server must derive the tenant from a verified, stable identity claim; it must never accept a tenant ID from tool arguments as proof of identity. The verifier must also populate the SDK `AccessToken.subject` field; the application rejects tokens with a missing/blank subject or missing/invalid `tenant_id` claim.
4. Bind the verified principal to every memory, feedback, and workflow store operation on the server side. Fail closed when the request has no verified principal or required identity claim.
5. Keep local `stdio` explicitly single-user. Do not infer an HTTP identity from environment variables or a caller-provided argument.
6. Add transport-level integration tests that prove unauthenticated requests are rejected before tools run, invalid/expired tokens are rejected, and two authenticated principals cannot read or alter each other's data.

## Options considered

### Keep local stdio only until an identity provider is selected — chosen

- Advantages: preserves the working local workflow; avoids inventing authentication; keeps the security boundary explicit.
- Disadvantages: does not provide a hosted multi-user service yet.

### Add Streamable HTTP with a homemade static bearer-token table

- Advantages: can demonstrate the SDK's token-verification hook.
- Disadvantages: not a complete identity lifecycle, token issuance, revocation, rotation, or account recovery system; unsuitable as a production identity solution.

### Accept tenant IDs as MCP tool parameters

- Advantages: minimal implementation effort.
- Disadvantages: callers can impersonate other tenants; this is data partitioning, not authorization. Rejected.

## Consequences

- The current release remains a local single-user MCP application.
- Multi-user hosting is explicitly blocked until an authorization-server integration, server-side principal-to-tenant mapping, and HTTP security tests are complete.
- Existing tenant-aware SQLite storage remains useful, but is not represented as a security boundary on its own.
- Selecting an authorization provider and its issuer/resource URLs is a deployment decision that must be made before enabling HTTP.

## Implementation progress — 2026-11-22

- Added `build_authenticated_server()` as an opt-in factory. It requires an injected SDK-compatible verifier and AuthSettings, enforces HTTPS issuer/resource URLs and non-empty required scopes, and never starts a listener itself.
- The factory registers tenant-aware memory, feedback, and workflow tools. Each protected operation derives tenant scope from the verified request token; no tool accepts a tenant ID argument.
- Added unit tests for injected verifier/configuration and server-side tenant binding, plus an ASGI transport test for missing and rejected bearer tokens.
- This is an integration seam, not a production identity integration. No issuer-specific verifier, token issuance, real account-to-tenant mapping, expiry/audience verification against a live issuer, or production deployment is configured.

## Implementation gates

- [ ] Select and configure an OAuth 2.1 authorization server.
- [ ] Implement and test the SDK token verifier against that issuer.
- [ ] Define a stable, immutable principal-to-tenant mapping.
- [x] Inject server-derived tenant context into all memory, feedback, and workflow operations in the opt-in authenticated server factory.
- [ ] Add negative tests for missing, invalid, expired, wrong-audience, and insufficient-scope tokens.
- [ ] Add cross-tenant isolation tests through the actual HTTP transport (not only direct function calls).
- [ ] Configure TLS, secret management, logging redaction, rate limiting, and deployment hardening.
- [ ] Re-review security claims and update documentation only after all gates pass.

## References

- MCP Python SDK authorization guide: https://py.sdk.modelcontextprotocol.io/run/authorization/
- MCP authorization specification: https://modelcontextprotocol.io/specification/draft/basic/authorization
