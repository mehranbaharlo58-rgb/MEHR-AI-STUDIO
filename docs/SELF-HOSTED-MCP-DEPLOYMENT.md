# Self-hosted authenticated MCP service

This container packages the Python registry, matcher, bounded orchestrator,
and OIDC-protected Streamable HTTP endpoint. It is a deployment target for a
Linux host or container platform; adding the files does not deploy the service.

## Configure

1. Copy `.env.mcp.example` to `.env.mcp`. This file contains only the Python MCP service's environment and is intentionally separate from the Cloudflare Worker secrets.
2. Set the four required Python resource-server values:
   - `MEHR_OIDC_ISSUER_URL`
   - `MEHR_OIDC_JWKS_URL`
   - `MEHR_OIDC_AUDIENCE`
   - `MEHR_MCP_RESOURCE_URL`
3. Set `MEHR_ALLOWED_ORIGINS` to the exact HTTPS dashboard origin if the
   browser and MCP service use different origins.
4. Configure provider credentials server-side using `AI_BASE_URL`,
   `AI_API_KEY`, `AI_MODEL`, or the supported provider-specific secret
   environment. Never put provider keys in the browser or catalogue.
5. Ensure the identity provider issues short-lived RS256 access tokens with
   the configured audience, required scope, and a trusted tenant claim.

Do not commit `.env.mcp`. The Docker build context excludes environment files.

## Run

~~~bash
docker compose build
docker compose up -d
docker compose logs -f mehr-mcp
~~~

The service listens inside the container on port 8000. Compose publishes it
only on host loopback at `127.0.0.1:8000`. Put a TLS-terminating reverse proxy
in front of it and proxy the MCP path `/mcp` without stripping the
`Authorization`, `Mcp-Session-Id`, or `Mcp-Protocol-Version` headers. Do
not expose this service as public plaintext HTTP.

The SQLite registry is stored in the persistent `mehr-ai-data` volume at
`/data/mehr_ai_studio.sqlite3`. Back up this volume using the host's normal
persistent-volume procedure.

## Browser connection

In the Agent workspace, enter the public HTTPS MCP URL ending in `/mcp` and
a short-lived OIDC access token valid for the configured MCP audience. The
server's `MEHR_ALLOWED_ORIGINS` must include the exact GitHub Pages or custom
dashboard origin. The dashboard holds the access token in page memory only.

The separate Cloudflare Worker login used by MEHR Live is not automatically
valid for this Python MCP audience. Configure a matching OIDC client and
resource-server policy before expecting browser authentication to succeed.

## Operational limits

The service is not production-ready solely because the container builds.
Before launch, verify TLS, OIDC issuer/JWKS/audience/scope/tenant claims,
persistent storage, provider smoke tests, quotas, cost limits, logging and
redaction, backups, and Android/desktop browser operation. Production rollout
remains an explicit owner decision.
