# Cloudflare Worker deployment

Worker entrypoint: `cloudflare/worker.mjs`  
Wrangler configuration: `wrangler.jsonc`  
Worker script name: `mehr-ai-studio`  
Browser origin: `https://mehranbaharlo58-rgb.github.io`

## Deployment workflow

The `deploy-cloudflare-worker` GitHub Actions workflow:
1. Requires Cloudflare deployment credentials, OIDC configuration, and the OpenAI Realtime API key before deploying.
2. Verifies the Cloudflare API token and account access.
3. Deploys the Worker with Wrangler 4.168.0 and the checked-in Durable Object binding/migration.
4. Synchronizes OIDC, OpenAI, and optional Cloudflare SFU configuration into Worker secrets without printing values.

It runs on pushes to `main` that change Worker/config/workflow files, or by manual dispatch from the default branch. It does not deploy feature branches or pull requests. Keep production deployment behind the repository's normal review and approval controls.

## Required GitHub Actions secrets

Configure these under repository Settings → Secrets and variables → Actions:

- `CLOUDFLARE_API_TOKEN`: token with Workers Scripts edit/deploy permissions.
- `CLOUDFLARE_ACCOUNT_ID`: 32-character hexadecimal Account ID.
- `OIDC_ISSUER_URL`: exact HTTPS token issuer.
- `OIDC_JWKS_URL`: HTTPS JWKS endpoint.
- `OIDC_AUDIENCE`: expected API audience.
- `OIDC_CLIENT_ID`: public SPA client ID.
- `OIDC_AUTHORIZATION_URL`: HTTPS authorization endpoint.
- `OIDC_TOKEN_URL`: HTTPS token endpoint; it must allow browser PKCE token exchange from the GitHub Pages origin.
- `OIDC_REDIRECT_URI`: exact registered callback URI: `https://mehranbaharlo58-rgb.github.io/MEHR-AI-STUDIO/`.
- `OPENAI_API_KEY`: server-side key with access to the configured Realtime model.

Optional secrets:
- `OIDC_PUBLIC_SCOPES` (default `openid profile studio:access`).
- `OIDC_REQUIRED_SCOPES` (default `studio:access`).
- `OIDC_TENANT_CLAIM` (default `tenant_id`).
- `OPENAI_REALTIME_MODEL` (default `gpt-realtime-2.1`).
- `OPENAI_REALTIME_VOICE` (default `marin`).
- `CLOUDFLARE_SFU_APP_ID` and `CLOUDFLARE_SFU_APP_SECRET`: optional pair for the SFU camera relay. Supply both or neither.

Do not paste credentials into chat, commit them to Git, or expose them in browser code.

## Runtime behavior

The primary voice and sampled-image vision path uses direct OpenAI Realtime WebRTC. It requires OIDC and `OPENAI_API_KEY`. The Cloudflare SFU is an optional relay; it is not required for direct voice or the fallback sampled-image path. The Worker capability endpoint reports these two readiness states independently.

The existing text-generation endpoint remains a separate owner-token flow. Its legacy variables (`MEHR_API_TOKEN`, `AI_API_KEY`, `AI_BASE_URL`, `AI_MODEL`) are independent from the Realtime voice configuration. Do not treat the legacy text-generation endpoint as multi-user identity infrastructure.

## Post-deployment verification

- Check `GET /api/live/oidc/config` from the approved browser origin.
- Complete OIDC Authorization Code + PKCE login using the registered callback URI.
- Check authenticated `GET /api/live/capabilities`; it should report direct Realtime readiness independently from optional SFU readiness.
- Test actual audio, remote playback, sampled camera frames, camera stop, disconnect, and reconnect on Android and desktop.
- If SFU credentials are configured, verify real adapter frame delivery and viewer ticket replay rejection.

A Wrangler dry-run or successful Worker deployment does not prove provider connectivity or media delivery. The live product is not release-ready until real provider and device tests pass.
