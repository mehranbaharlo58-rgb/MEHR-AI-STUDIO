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

Authentication architecture decision: [ADR-0001 — Authentication boundary for multi-user MCP deployment](docs/adr/0001-authentication-boundary.md). The current release remains local single-user stdio; hosted multi-user operation is blocked until the implementation gates in that ADR are completed and tested. A fail-closed identity resolver now maps the SDK-verified token's trusted `tenant_id` claim to a tenant (`src/mehr_ai_studio/auth_context.py`); it is a foundation only and is not yet wired into the public tool registry or an HTTP deployment. The MCP SDK minimum is pinned to 1.27.2 because that release line provides the `AccessToken.claims` field used by the resolver.
- Secrets are read from environment variables and are never intentionally included in error messages.
- Project memory is stored in local SQLite by default; it is not encrypted at rest by this application.
- The current MCP tools run as a local, single-user stdio process. They do not authenticate users or derive tenant IDs from an authenticated principal.
- `StudioStore` supports tenant-scoped records, but its `tenant_id` argument is a data-partitioning parameter, not an authentication or authorization boundary. The exposed MCP tools currently use the default tenant.
- Do not share one running instance or expose a network endpoint to multiple users. A multi-user deployment requires authenticated identity resolution, server-controlled tenant binding on every operation, authorization tests, TLS, and deployment hardening.
- No automatic publication, payments, or irreversible external actions are performed.
- Content assessment is structural only; it does not verify factual accuracy, originality, or legal compliance.
- Feedback is analytics data, not model training.
- Sending a prompt to a configured external provider transmits that prompt and any included context to that provider. Do not include confidential data unless the provider and data handling are approved.

## Roadmap
- [x] Repository and modular package
- [x] SQLite memory and feedback store
- [x] Optional AI provider adapter
- [x] MCP tools and content workflow
- [x] Unit and workflow tests
- [x] CI lint, test, and package-build checks
- [ ] Live provider integration test with a real configured provider
- [ ] Deployment, authentication, monitoring, and operational hardening
- [ ] Public release review and installation validation

## License
No open-source license has been selected. All rights remain with the project owner unless a license is added.
