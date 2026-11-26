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
proxy headers by default.

For browser clients on a different origin, set MEHR_ALLOWED_ORIGINS to a comma-separated allowlist of exact HTTPS origins (for example, https://studio.example.com). Wildcards are rejected. Authorization and MCP session/protocol headers are allowed; credentials mode is disabled. Leave this variable unset for same-origin or server-to-server use.

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

The Agent workspace includes a browser-side MCP Streamable HTTP client. It
connects to the authenticated server's `/mcp` endpoint, initializes a session,
lists tools, reads the caller's tenant-scoped model registry, seeds the curated
catalogue on an explicit first connection when the registry is empty, and can
dispatch a task through `execute_ai_task`.

The user supplies a short-lived OIDC access token issued by the same identity
provider configured for this MCP resource server. The dashboard keeps that
token in page memory only; it is not written to localStorage or sessionStorage,
and is cleared when the user disconnects or reloads the page. The separate
Cloudflare Worker OIDC login in the Live room is not assumed to issue a token
valid for this MCP audience. The endpoint must use HTTPS and
`MEHR_ALLOWED_ORIGINS` must include the exact dashboard origin for
cross-origin access.

The browser client does not receive provider API keys. Provider credentials
remain in the server's secret environment and the MCP server's existing
connector configuration. A model is not considered operational until the
server reports it as configured or tested after a successful connector test.
Catalogue seeding does not configure credentials or mark integrations tested.

A production release still requires a reviewed OIDC authorization-code + PKCE
client for this MCP audience, same-origin/reverse-proxy routing or narrowly
scoped CORS, rate limits, quota enforcement, secret redaction, monitoring,
persistent storage, and live end-to-end tests against the selected identity
provider. Passing local unit tests does not prove live identity-provider or
production connectivity.
 
## Validation status

Automated tests verify the HTTP app factory, loopback default, proxy-header
trust setting, invalid port rejection, token rejection, and tenant isolation.
They do not prove a real IdP integration, public TLS configuration, live
provider connectivity, or production deployment.
