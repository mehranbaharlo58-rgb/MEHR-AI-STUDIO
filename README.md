# MEHR AI STUDIO

An extensible AI production studio built around reusable workflows, project memory, quality checks, and provider-independent model adapters.

> Status: early development. The repository is the source of truth. Features are considered complete only after automated tests and integration checks pass.

## Product direction
- Store explicit project and brand context in a local database.
- Convert briefs into structured content plans and production prompts.
- Assess output against configurable structural quality criteria.
- Record human feedback to improve workflow decisions.
- Connect compatible AI providers through replaceable adapters.
- Expose capabilities through an MCP server.

Feedback storage is **not** model training. The system does not silently train or fine-tune a model.

## Current foundation — 0.4.1
- Modular Python package and environment-based configuration.
- Persistent SQLite storage for project context and human feedback.
- OpenAI-compatible chat-completions adapter with response validation.
- MCP tools for status, memory, content planning, quality review, generation, and workflow orchestration.
- Automated tests, lint checks, and package-build verification in GitHub Actions.

## Requirements
- Python 3.11+
- Install development dependencies: `pip install -e ".[dev]"`

## Local development
```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"
ruff check src tests
pytest -q
python -m build
```

Run the MCP server with `python -m mehr_ai_studio`. It uses stdio by default.

## AI provider configuration
Copy `.env.example` to `.env`, then set:
- `AI_BASE_URL`: provider API base URL, normally ending in `/v1`.
- `AI_API_KEY`: provider secret key.
- `AI_MODEL`: model identifier supported by that provider.
- `AI_TIMEOUT_SECONDS`: request timeout in seconds.

The adapter appends `/chat/completions` unless the supplied base URL already ends with that path. Provider compatibility must be verified against the selected service. Never commit `.env`, API keys, access tokens, database files, or private user data.

## Security and limitations

Authentication architecture decision: [ADR-0001 — Authentication boundary for multi-user MCP deployment](docs/adr/0001-authentication-boundary.md). The current release remains local single-user stdio; hosted multi-user operation is blocked until the implementation gates in that ADR are completed and tested. A fail-closed identity resolver requires a non-empty verified token subject and maps the SDK-verified token's trusted `tenant_id` claim to a tenant (`src/mehr_ai_studio/auth_context.py`). An opt-in authenticated server factory (`src/mehr_ai_studio/authenticated_server.py`) now accepts an injected SDK `TokenVerifier` and `AuthSettings`, requires HTTPS issuer/resource URLs and at least one required scope, and binds memory, feedback, and workflow operations to the request's verified tenant. It builds a server but does not start or expose a network listener. A standards-based RS256 OIDC/JWT verifier is now implemented in `src/mehr_ai_studio/oidc.py`: it resolves signing keys from the configured HTTPS JWKS endpoint, validates signature, exact issuer, audience, expiry, issued-at/not-before, subject, client identity, required scopes, and the signed tenant claim. `build_oidc_authenticated_server_from_env()` wires it to environment configuration. The local `stdio` server remains the only default entry point; OIDC HTTP hosting is opt-in and requires real issuer values and an account system that issues the `tenant_id` claim. The MCP SDK minimum is pinned to 1.27.2 because that release line provides the `AccessToken.claims` field used by the resolver.
- Secrets are read from environment variables and are never intentionally included in error messages.
- Project memory is stored in local SQLite by default; it is not encrypted at rest by this application.
- The default MCP entry point remains a local, single-user stdio process. The opt-in authenticated factory is separate and is not activated by default.
- `StudioStore` supports tenant-scoped records, but its `tenant_id` argument is only a data-partitioning parameter. Only the opt-in authenticated factory supplies it from the verified request context.
- Do not deploy the opt-in factory until a real provider-specific verifier has been implemented and tested against the selected issuer, including signature/introspection, issuer, audience/resource, expiry, scopes, and stable tenant mapping. Actual HTTP transport tests, TLS, secret management, logging redaction, rate limiting, and deployment hardening remain mandatory.
- No automatic publication, payments, or irreversible external actions are performed.
- Content assessment is structural only; it does not verify factual accuracy, originality, or legal compliance.
- Feedback is analytics data, not model training.
- Sending a prompt to a configured external provider transmits that prompt and any included context to that provider. Do not include confidential data unless the provider and data handling are approved.

## Competitive research

A source-informed review of ten leading AI workflow, agent, memory, and MCP projects is available in [Competitive Architecture Review — 2026-11-22](docs/competitive-analysis-2026-11-22.md). It records inspected upstream files, license constraints, reusable patterns, current MEHR gaps, and the recommended implementation sequence.

## Roadmap
- [x] Repository and modular package
- [x] SQLite memory and feedback store
- [x] Optional AI provider adapter
- [x] MCP tools and content workflow
- [x] Unit and workflow tests
- [x] CI lint, test, and package-build checks
- [ ] Live provider integration test with a real configured provider
- [x] OIDC/JWT verifier implementation and cryptographic claim tests
- [ ] Configure a real issuer, provision tenant claims/scopes, and test with live-issued tokens
- [ ] Deployment, authentication, monitoring, and operational hardening
- [ ] Public release review and installation validation

## License
No open-source license has been selected. All rights remain with the project owner unless a license is added.
