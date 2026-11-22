# Local MVP Quick Start

MEHR AI STUDIO 0.4.1 is currently distributed as a GitHub Actions artifact, not as a public PyPI package.

## 1. Download the tested package

1. Open the [successful CI run for the current PR head](https://github.com/mehranbaharlo58-rgb/MEHR-AI-STUDIO/actions/runs/45021476184).
2. Download the `mehr-ai-studio-distributions` artifact and extract the ZIP.
3. Use the `.whl` file inside the extracted folder.

Verified artifact metadata:
- Artifact ID: `14754111037`
- SHA-256: `a4ffb9b3271bef30454fae52a3eaaf7311dc26549cd955d5cdbff4f5332c1f23`
- CI run: `45021476184` (run #257)
- CI commit: `ae8aedc25058d8dc6b94fc24fd9fb64f94338b43`
- Size: 58,203 bytes
- Expires: `2026-12-06 12:17:35 UTC`

After downloading the ZIP, verify its integrity before extracting:

```powershell
Get-FileHash .\\mehr-ai-studio-distributions.zip -Algorithm SHA256
```

```bash
sha256sum mehr-ai-studio-distributions.zip
```

The computed hash must match the SHA-256 value above.

## 2. Install

Requires Python 3.11 or newer.

### Windows PowerShell

```powershell
py -3.11 -m venv .venv
.\\.venv\\Scripts\\Activate.ps1
python -m pip install .\\mehr_ai_studio-0.4.1-py3-none-any.whl
mehr-ai-studio-check
```

### macOS / Linux

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install ./mehr_ai_studio-0.4.1-py3-none-any.whl
mehr-ai-studio-check
```

Replace the wheel filename with the exact filename in the downloaded artifact if it differs.

## 3. Run the MCP server

After installation:

```bash
mehr-ai-studio
```

The server uses MCP over stdio. Do not run it in a terminal and expect a chat interface; configure your MCP-compatible client to launch this command as a local stdio server. The exact client configuration format depends on the client.

### MCP client configuration template

For a client that accepts a JSON MCP server configuration, use this template and replace every placeholder with an absolute path and your own provider settings. Keep the API key in the client's private environment configuration; do not commit this file.

Windows example:

```json
{
  "mcpServers": {
    "mehr-ai-studio": {
      "command": "C:\\\\ABSOLUTE\\\\PATH\\\\TO\\\\.venv\\\\Scripts\\\\python.exe",
      "args": ["-m", "mehr_ai_studio"],
      "cwd": "C:\\\\ABSOLUTE\\\\PATH\\\\TO\\\\MEHR-AI-STUDIO",
      "env": {
        "AI_BASE_URL": "https://YOUR-PROVIDER.example/v1",
        "AI_API_KEY": "YOUR-PRIVATE-API-KEY",
        "AI_MODEL": "YOUR-MODEL-ID"
      }
    }
  }
}
```

macOS/Linux example:

```json
{
  "mcpServers": {
    "mehr-ai-studio": {
      "command": "/absolute/path/to/MEHR-AI-STUDIO/.venv/bin/python",
      "args": ["-m", "mehr_ai_studio"],
      "cwd": "/absolute/path/to/MEHR-AI-STUDIO",
      "env": {
        "AI_BASE_URL": "https://YOUR-PROVIDER.example/v1",
        "AI_API_KEY": "YOUR-PRIVATE-API-KEY",
        "AI_MODEL": "YOUR-MODEL-ID"
      }
    }
  }
}
```

This is a configuration template, not a verified client-specific setup. Consult the selected MCP client's documentation for its config-file location and restart it after editing.

## 4. Configure an AI provider

Set these environment variables in the environment inherited by the MCP client:

- `AI_BASE_URL`: OpenAI-compatible API base URL, normally ending in `/v1`.
- `AI_API_KEY`: provider API key.
- `AI_MODEL`: model identifier.
- `AI_TIMEOUT_SECONDS`: optional request timeout; default is 45 seconds.

Optional retry controls:
- `AI_MAX_ATTEMPTS`: 1–5; default 3.
- `AI_RETRY_BACKOFF_SECONDS`: 0–10; default 0.5.

Without provider credentials, local storage, brief creation, and structural assessment remain available, but AI generation is not active. Never commit API keys or put them in screenshots or support logs.

## Scope and limitations

- Local, single-user MCP server; no hosted service or browser-based studio UI is included.
- SQLite data is stored locally and is not encrypted at rest by this application.
- Structural assessment does not fact-check, verify originality, or establish legal compliance.
- A configured external provider receives prompts and any context sent with them.
- Hosted multi-tenant OIDC/HTTP operation is not approved for production.
- This CI artifact is a tested build, not a signed installer or public package release.
