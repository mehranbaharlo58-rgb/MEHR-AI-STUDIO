# Authenticated MCP HTTP deployment

This service is an opt-in authenticated MCP transport. It is not enabled by the
default local mehr-ai-studio stdio command.

## Start locally

Install the package (the uvicorn runtime is included), configure the OIDC
environment variables below, then run:

~~~bash
mehr-ai-studio-http
~~~

The default listener is 127.0.0.1:8000. Override it only when the hosting
platform requires a public container bind:

- MEHR_HTTP_HOST (default 127.0.0.1)
- MEHR_HTTP_PORT (default 8000)

For a public deployment, bind to the platform-required interface and terminate
TLS at a trusted ingress/reverse proxy. Do not expose the service over plaintext
HTTP on a public network. The application deliberately does not trust forwarded
proxy headers by default.\n\nFor browser clients on a different origin, set MEHR_ALLOWED_ORIGINS to a comma-separated allowlist of exact HTTPS origins (for example, https://studio.example.com). Wildcards are rejected. Authorization and MCP session/protocol headers are allowed; credentials mode is disabled. Leave this variable unset for same-origin or server-to-server use.

## Required OIDC resource-server configuration

- MEHR_OIDC_ISSUER_URL: exact HTTPS issuer URL.
- MEHR_OIDC_JWKS_URL: HTTPS JWKS endpoint for RS256 signing keys.
- MEHR_OIDC_AUDIENCE: audience expected in access tokens.
- MEHR_MCP_RESOURCE_URL: HTTPS resource URL registered with the IdP.
- MEHR_OIDC_REQUIRED_SCOPES: whitespace-separated required scopes
  (default studio:access).
- MEHR_OIDC_TENANT_CLAIM: trusted tenant claim name (default tenant_id).

The issuer must issue access tokens with a stable subject, client identity,
the configured audience, all required scopes, and a valid tenant claim. The
verifier accepts RS256 only and validates signature, issuer, audience, expiry,
issued-at/not-before, client identity, scopes, and tenant format. Use access
tokens with a lifetime no longer than 24 hours.

## Provider and storage configuration

- AI_BASE_URL, AI_API_KEY, AI_MODEL configure the optional
  fallback OpenAI-compatible provider.
- MEHR_AI_API_KEY_PROVIDER_SLUG can hold provider-specific connector keys.
- MEHR_DB_PATH selects the SQLite database path.

Keep secrets in the hosting platform's secret manager, never in source control,
browser storage, model registry metadata, or deployment logs. The SQLite file
must be on persistent storage and protected by the host's filesystem controls.

## Browser integration boundary

The HTTP entry point exposes the MCP Streamable HTTP protocol at the MCP SDK's
default endpoint. A browser application must obtain an access token from the
same configured identity provider and speak the Streamable HTTP protocol. The
current static dashboard still calls the separate single-provider Cloudflare
Worker; it is not connected to this MCP service. Do not put a server-side
provider key or a long-lived owner token in browser JavaScript.

A browser-facing product release still requires a reviewed OIDC authorization
code + PKCE client, same-origin/reverse-proxy routing or narrowly scoped CORS,
rate limits, quota enforcement, secret redaction, monitoring, persistent
storage, and live end-to-end tests against the selected identity provider.
No live issuer, provider, or public deployment is configured by this change.

## Validation status

Automated tests verify the HTTP app factory, loopback default, proxy-header
trust setting, invalid port rejection, token rejection, and tenant isolation.
They do not prove a real IdP integration, public TLS configuration, live
provider connectivity, or production deployment.
