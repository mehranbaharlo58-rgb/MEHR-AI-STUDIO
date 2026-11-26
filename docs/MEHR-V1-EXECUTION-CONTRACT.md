# MEHR AI STUDIO — Version 1 execution contract

## Product boundary

Version 1 is the core Agent Stack product: a polished bilingual workspace, a central model/agent registry and orchestrator, and working live voice plus camera-based visual input. Desktop control, USB/Wi-Fi pairing, autonomous desktop operation, and secondary automation modules are explicitly deferred.

## The 20 delivery gates

| # | Gate | Evidence / status |
|---:|---|---|
| 1 | Freeze V1 scope | Done: this contract |
| 2 | Define provider-neutral model record | Existing Pydantic AIModel contract |
| 3 | Define honest operational states | Done: catalog_only/configured/tested/degraded/disabled |
| 4 | Add bounded 1–100 dispatch contract | Existing execution manager |
| 5 | Add task-to-model matching | Existing explainable matcher |
| 6 | Persist registry in SQLite | Existing tenant-scoped registry store |
| 7 | Seed exactly 100 catalogue candidates | Existing seed + test |
| 8 | Preserve operator edits on reseed | Existing idempotency test |
| 9 | Publish catalogue to static UI | Done: ui/ai-catalog.json |
| 10 | Build Agent workspace screen | Done: bilingual catalogue, search, category/status filters |
| 11 | Show honest connection counters | Done: catalogue/configured/tested are separate |
| 12 | Escape catalogue content in UI | Done: safe text renderer + regression test |
| 13 | Validate inline UI JavaScript | Existing Node VM syntax test |
| 14 | Validate 100 unique catalogue IDs | Done: new UI regression test |
| 15 | Wire UI task composer to authenticated orchestrator API | Done at code level: browser MCP client initializes authenticated sessions, reads tenant registry, seeds empty registry and dispatches tasks; live IdP test pending |
| 16 | Add provider credentials UI without exposing secrets | Pending: provider keys remain server-side; secure server secret provisioning documented, no browser key form |
| 17 | Add provider-specific adapters and live smoke tests | Partial: OpenAI-compatible adapter exists; live provider proof pending |
| 18 | Finish real-time audio end-to-end verification | Partial: browser/Worker path exists; provider/device test pending |
| 19 | Verify camera vision path end-to-end | Partial: sampled image and SFU bridge code exists; deployed provider/device test pending |
| 20 | Release gate: integration, security, cost, mobile/desktop QA | Pending; no production release authorized |

## Agent catalogue semantics

The 100 records are curated discovery candidates. They are not 100 live integrations and must not be represented as such. A model is selectable for execution only when it has a supported adapter, valid credentials, and operational status. tested is earned only after a successful explicit smoke test. Web-only products, SDKs, MCP servers, and native APIs remain distinct access modes; a product website is not an API endpoint.

## V1 acceptance criteria

- The Agent workspace is usable in Persian and English on desktop and mobile widths.
- Search and category/status filters operate on the 100-record catalogue.
- The dashboard distinguishes catalogue count, configured count, tested count, and pending count.
- No catalog-only model is presented as connected or runnable.
- The orchestration API authenticates users, applies per-user quotas, bounds fan-out and timeouts, and isolates provider failures.
- Secrets are never stored in catalogue metadata or committed to the repository.
- Live voice and visual input are verified with a real configured provider on supported devices.
- Production deployment remains gated on owner approval and external provider credentials.

## Current implementation boundary

The Agent workspace can now connect directly to the opt-in authenticated Python
MCP service over Streamable HTTP. It can initialize an authenticated session,
read the caller's tenant-scoped registry, seed the 100-entry catalogue into an
empty tenant registry, and dispatch a task to configured adapters. It also
keeps the access token in page memory only and clears it on disconnect/reload.

This is a code-level integration, not a live deployment. It requires a running
HTTPS MCP service, a correctly configured OIDC issuer/audience/scope/tenant
claim, an exact CORS origin allowlist when cross-origin, and a short-lived token
valid for this MCP resource. The separate Cloudflare Worker login is not
automatically valid for the Python MCP audience. Provider keys remain on the
server; no API-key entry field is exposed to the browser.

Remaining release blockers are live identity-provider validation, server-side
provider credential provisioning, successful provider smoke tests, real
Android/desktop voice and camera verification, and release security/cost/QA.
