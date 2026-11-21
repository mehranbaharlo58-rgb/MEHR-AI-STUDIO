# MEHR AI STUDIO

An extensible AI production studio built around reusable workflows, project memory, quality checks, and provider-independent model adapters.

> Status: early development. This repository is the source of truth. Features are complete only after tests and integration checks pass.

## Product direction
- Store explicit project and brand context in a local database.
- Convert briefs into structured content plans and production prompts.
- Assess output against configurable quality criteria.
- Record human feedback to improve workflow decisions.
- Connect compatible AI providers through replaceable adapters.
- Expose capabilities through an MCP server.

Feedback storage is **not** model training. The system does not silently train or fine-tune a model.

## Milestone 0.4 — reliable foundation
1. Modular Python package and configuration.
2. Persistent SQLite storage for project context and feedback.
3. Provider adapter with safe failure handling.
4. MCP tools for status, memory, content planning, and quality review.
5. Automated tests and documented local setup.

## Requirements
- Python 3.11+
- Install: `pip install -e ".[dev]"`

## Local development
```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"
pytest -q
```

Run: `python -m mehr_ai_studio`

The server uses stdio by default. Do not expose an HTTP endpoint publicly without authentication, TLS, and deployment hardening.

## Configuration
Copy `.env.example` to `.env`. Never commit API keys, access tokens, database files, or private user data.

## Security
- Secrets are read from environment variables.
- User data remains local by default.
- No automatic publication, payments, or irreversible actions.
- Human approval is required before external actions.
- Logs must avoid secrets and sensitive prompt content.

## Roadmap
- [x] Repository initialized
- [x] Core package, SQLite memory, feedback store, provider adapter, and tests
- [ ] MCP integration tests and CI verification
- [ ] Live provider integration tests
- [ ] Deployment and monitoring
- [ ] Public release review

## License
No open-source license has been selected. All rights remain with the project owner unless a license is added.
