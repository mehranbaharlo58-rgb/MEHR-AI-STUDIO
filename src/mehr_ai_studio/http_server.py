"""Opt-in authenticated Streamable HTTP entry point.

TLS must terminate at a trusted reverse proxy or hosting platform. The default
bind is loopback so importing or starting this entry point does not expose a
public listener accidentally.
"""

from __future__ import annotations

import os

from .authenticated_server import build_oidc_authenticated_server_from_env


def create_app():
    """Build the OIDC-protected MCP ASGI application from environment settings."""
    server = build_oidc_authenticated_server_from_env()
    return server.streamable_http_app()


def main() -> None:
    """Run the authenticated MCP service; public binding is an explicit choice."""
    host = os.getenv("MEHR_HTTP_HOST", "127.0.0.1").strip()
    port_text = os.getenv("MEHR_HTTP_PORT", "8000").strip()
    try:
        port = int(port_text)
    except ValueError as exc:
        raise ValueError("MEHR_HTTP_PORT must be an integer") from exc
    if not host or not 1 <= port <= 65535:
        raise ValueError("MEHR_HTTP_HOST and a valid MEHR_HTTP_PORT are required")

    import uvicorn

    uvicorn.run(
        create_app(),
        host=host,
        port=port,
        proxy_headers=False,
    )


if __name__ == "__main__":
    main()
