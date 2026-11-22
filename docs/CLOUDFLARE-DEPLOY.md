# Cloudflare Worker API deployment

This is an initial, single-owner HTTP generation adapter. It does not turn the existing local SQLite/MCP application into a multi-user hosted service. It exposes only health and text-generation endpoints; project memory, workflow history, file storage, OAuth accounts, and multi-tenant access are not implemented here.

## Runtime

- Worker entrypoint: `cloudflare/worker.mjs`
- Configuration: `wrangler.jsonc`
- Browser origin: the existing GitHub Pages site, restricted by `ALLOWED_ORIGIN`
- Provider credentials and owner token must be configured as Cloudflare Worker secrets, never committed to Git.

## Required Worker secrets

Configure these under the Worker settings in Cloudflare:

- `MEHR_API_TOKEN`: a randomly generated owner-only bearer token of at least 32 characters.
- `AI_BASE_URL`: HTTPS OpenAI-compatible API base URL, normally ending in `/v1`.
- `AI_API_KEY`: provider API key.
- `AI_MODEL`: model identifier supported by that provider.

The non-secret `ALLOWED_ORIGIN` is already set to the current GitHub Pages origin in `wrangler.jsonc`. If the site hostname changes, update it before deployment.

## Endpoints

- `GET /api/health`: returns service and provider-configuration status; it does not expose secrets.
- `POST /api/generate`: requires `Authorization: Bearer <MEHR_API_TOKEN>` and JSON `{"prompt":"..." }`.

The API rejects other browser origins, requires HTTPS for the upstream provider, limits request size and prompt length, does not log prompt contents, and never returns provider credentials. Provider redirects are not followed, preventing the bearer credential from being forwarded to a redirect destination. Provider responses must be JSON and are capped at 1 MiB. The owner token is an access credential: do not publish it or embed it in a public source file.

## Deployment boundary

Connect this repository to Cloudflare Workers Builds and select `wrangler.jsonc` as the Wrangler configuration. Deploy only after setting the four required variables/secrets. Verify the health endpoint, then test generation using the owner token. Do not enable public multi-user access: this initial adapter is single-owner only and has no account lifecycle, durable rate limiting, or persistent workflow database.

The GitHub Pages UI is connected to this API, but the Worker itself must still be deployed and configured separately. File upload/content processing is not implemented in the UI/API integration.
