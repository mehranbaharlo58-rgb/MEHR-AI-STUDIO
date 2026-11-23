# Cloudflare Worker API deployment

This is an initial, single-owner HTTP generation adapter. It does not turn the existing local SQLite/MCP application into a multi-user hosted service. It exposes only health and text-generation endpoints; project memory, workflow history, file storage, OAuth accounts, and multi-tenant access are not implemented here.

## Runtime

- Worker entrypoint: `cloudflare/worker.mjs`
- Configuration: `wrangler.jsonc`
- Browser origin: the existing GitHub Pages site, restricted by `ALLOWED_ORIGIN`
- Provider credentials and owner token must be configured in Cloudflare, never committed to Git.

## Step 1 — Deploy the Worker

A manually triggered workflow is available at **Actions → deploy-cloudflare-worker → Run workflow**. Before using it, add these two repository Actions secrets under **Settings → Secrets and variables → Actions**:

- `CLOUDFLARE_API_TOKEN`: Cloudflare API token with permission to edit Workers Scripts for the target account.
- `CLOUDFLARE_ACCOUNT_ID`: the target Cloudflare account ID.

Find the Account ID in Cloudflare Dashboard → **Workers & Pages** → **Overview** → **Account Details**. Copy the 32-character hexadecimal **Account ID** (not the Zone ID, account name, or user ID). The deployment workflow validates its format and checks that the token can access the account's Workers Scripts API before running Wrangler.

Run the workflow once to create/update the Worker. The workflow does not need the AI provider key or owner token and does not create or overwrite Worker runtime secrets.

## Step 2 — Configure Worker runtime values

After the first deployment, open the Worker **mehr-ai-studio-api** in Cloudflare and add the following runtime bindings under Settings → Variables and Secrets:

- `MEHR_API_TOKEN`: a randomly generated owner-only bearer token of at least 32 characters. Store it as a secret.
- `AI_API_KEY`: provider API key. Store it as a secret.
- `AI_BASE_URL`: HTTPS OpenAI-compatible API base URL, normally ending in `/v1`. A variable or secret is acceptable.
- `AI_MODEL`: model identifier supported by that provider. A variable or secret is acceptable.

Do not put provider credentials or `MEHR_API_TOKEN` in source code, GitHub workflow files, or chat messages. Keep the owner token private; it is entered only in the dashboard's Settings panel in the browser session.

The non-secret `ALLOWED_ORIGIN` is already set to the current GitHub Pages origin in `wrangler.jsonc`. If the site hostname changes, update it before deployment.

## Endpoints

- `GET /api/health`: returns service and provider-configuration status; it does not expose secrets.
- `POST /api/generate`: requires `Authorization: Bearer <MEHR_API_TOKEN>` and JSON `{"prompt":"..." }`.

The API rejects other browser origins, requires HTTPS for the upstream provider, limits request size and prompt length while streaming the request body, does not log prompt contents, and never returns provider credentials. Provider redirects are not followed, preventing the bearer credential from being forwarded to a redirect destination. Provider responses must be JSON and are capped at 1 MiB.

## Deployment boundary

After configuring runtime values, verify the health endpoint, then test generation using the owner token. Do not enable public multi-user access: this initial adapter is single-owner only and has no account lifecycle, durable rate limiting, or persistent workflow database.

The GitHub Pages UI is connected to this API, but the Worker itself must still be deployed and configured separately. File upload/content processing is not implemented in the UI/API integration.
