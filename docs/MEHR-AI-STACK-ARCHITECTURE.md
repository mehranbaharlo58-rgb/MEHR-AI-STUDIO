# MEHR AI STACK — Architecture Baseline

Status: proposed implementation baseline  
Branch: `feat/universal-ai-stack-core`

## Product definition

A provider-independent control plane to catalogue, match, connect, dispatch, and observe AI models and tools across common work domains. The target catalogue is 100 entries. Catalogue size is not equivalent to 100 working integrations.

## Operational states

- `catalog_only`: researched entry; no connector verified.
- `configured`: connector configuration exists; no successful live call yet.
- `tested`: integration smoke test succeeded with evidence.
- `degraded`: connector exists but is unhealthy.
- `disabled`: deliberately unavailable.

## Architecture

1. **AI Registry:** canonical metadata for provider, model/tool, domain, capabilities, modalities, access mode, availability, status, concurrency, quality and latency.
2. **Intelligent Matcher:** explainable ranking using task, category, required capabilities, modalities, tags, free/local preference and measured signals.
3. **Connector Layer:** native API, OpenAI-compatible API, local runtime, MCP and web-only products remain distinct integration types. A website is not an API connector.
4. **Execution Manager:** bounded parallel dispatch, per-model concurrency limits and isolated provider failures.
5. **Verification & Observability:** smoke tests, latency/error measurements, provenance and health.
6. **Dashboard:** registry browser, task composer, match explanations, parallel run and result comparison.

## First implementation increment

Strict model/request contracts, registry upsert/filter/list, deterministic matching, bounded parallel dispatch and tests. The registry is intentionally separated from provider-specific code. Persistence and real adapters are subsequent increments.

## Non-goals

- Claiming that 100 entries are connected.
- Bypassing authentication, regional availability, rate limits or provider terms.
- Browser automation of products without a supported integration path.
- Unbounded fan-out to all 100 models for every task.
- Triggering paid or irreversible operations without owner approval.

## Acceptance gates

- [ ] Registry persistence and migrations.
- [ ] 100 sourced entries with last-verified date and access evidence.
- [ ] At least 5 real connectors pass live smoke tests.
- [ ] Offline matching tests and explanations.
- [ ] Parallel execution respects global and per-provider limits.
- [ ] Timeouts, cancellation and provider failures are bounded.
- [ ] Secrets are stored outside registry metadata.
- [ ] Usage, rate limits and tenant quotas before public exposure.

Engineering rule: always report catalogued, configured, tested, degraded and disabled counts separately.
