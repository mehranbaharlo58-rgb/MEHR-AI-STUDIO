# MEHR Live non-production provisioning and deployment

Status: deployment automation prepared; credentials and real provider verification remain external prerequisites.

## Architecture boundary

- The primary voice and sampled-image vision path is direct OpenAI Realtime WebRTC. It requires a valid OIDC access token and the Worker-only `OPENAI_API_KEY`.
- The Cloudflare Realtime SFU is an optional media relay for the camera bridge. It is not a prerequisite for direct voice or the fallback sampled-image path.
- `LIVE_SESSIONS` is the Durable Object binding used by the optional SFU bridge.
- The browser origin is `https://mehranbaharlo58-rgb.github.io`; the exact OIDC redirect URI is `https://mehranbaharlo58-rgb.github.io/MEHR-AI-STUDIO/`.

## Required GitHub Actions secrets

Set these in the repository's Settings → Secrets and variables → Actions. Do not paste secret values into issues, source files, or chat.

| Secret | Purpose |
|---|---|
| `CLOUDFLARE_API_TOKEN` | Cloudflare token with Workers Scripts edit/deploy permissions |
| `CLOUDFLARE_ACCOUNT_ID` | 32-character Cloudflare Account ID |
| `OIDC_ISSUER_URL` | Exact HTTPS issuer from the identity provider |
| `OIDC_JWKS_URL` | HTTPS JSON Web Key Set endpoint |
| `OIDC_AUDIENCE` | API audience expected in access tokens |
| `OIDC_CLIENT_ID` | Public SPA client ID registered at the identity provider |
| `OIDC_AUTHORIZATION_URL` | HTTPS authorization endpoint |
| `OIDC_TOKEN_URL` | HTTPS token endpoint; provider must permit browser PKCE token exchange (CORS) |
| `OIDC_REDIRECT_URI` | Exact callback URI shown above, including trailing slash |
| `OPENAI_API_KEY` | Server-side OpenAI API key with access to the configured Realtime model |

Optional OIDC secrets: `OIDC_PUBLIC_SCOPES` (default `openid profile studio:access`), `OIDC_REQUIRED_SCOPES` (default `studio:access`), and `OIDC_TENANT_CLAIM` (default `tenant_id`).

Optional direct Realtime settings: `OPENAI_REALTIME_MODEL` (default `gpt-realtime-2.1`) and `OPENAI_REALTIME_VOICE` (default `marin`).

## Optional SFU relay secrets

Provide both or neither:

- `CLOUDFLARE_SFU_APP_ID`
- `CLOUDFLARE_SFU_APP_SECRET`

If these are omitted, direct Realtime voice and sampled-image vision remain enabled when OIDC and OpenAI are configured; only the SFU bridge is disabled. The UI falls back to sampled JPEG frames over the Realtime data channel.

## Deployment workflow behavior

The `deploy-cloudflare-worker` workflow now:
1. Checks all mandatory secret names before deploying and rejects partial SFU credential pairs.
2. Verifies the Cloudflare API token is active and can access the target account.
3. Deploys the Worker using Wrangler 4.168.0 and the checked-in Durable Object binding/migration.
4. Synchronizes configured OIDC, OpenAI, and optional SFU values as Worker secrets without printing their values.

The Worker script name is `mehr-ai-studio`, as declared in `wrangler.jsonc`. The workflow deploys only from `main` or an explicit manual dispatch on the default branch. A feature-branch push does not deploy production.

## Provider-side identity setup

At the identity provider, register a public SPA client:
- Authorization Code flow enabled.
- PKCE with S256 required.
- No client secret in the browser.
- Exact redirect URI match, including path and trailing slash.
- Token endpoint CORS must allow the GitHub Pages origin.
- Access tokens must contain the configured audience, issuer, subject, tenant claim, client identifier (`azp` or `client_id`), expiry/issued-at claims, and required scope.

Do not invent issuer, audience, tenant claim, or endpoints. Copy them from the selected provider's metadata and application configuration.

## Verification gates after provisioning

- [ ] Deploy workflow completes successfully and applies the Durable Object migration.
- [ ] `/api/live/oidc/config` returns the public SPA configuration and the exact callback URI.
- [ ] Browser login completes PKCE exchange and receives an access token.
- [ ] `/api/live/capabilities` reports direct Realtime voice/vision enabled and independently reports SFU bridge readiness.
- [ ] A real audio call connects, returns remote audio, and handles disconnect/reconnect.
- [ ] Camera consent starts sampled-image delivery; stopping the camera stops image transmission without unnecessarily ending audio.
- [ ] Optional SFU bridge delivers frames and rejects replayed viewer tickets.
- [ ] Android and desktop browser tests are recorded.

A successful Worker deploy or mocked CI test is not proof of real media delivery. Do not mark the live product released until the provider and device gates pass.
