"""Opt-in authenticated Streamable HTTP entry point.

TLS must terminate at a trusted reverse proxy or hosting platform. The default
bind is loopback so importing or starting this entry point does not expose a
public listener accidentally.
"""

from __future__ import annotations

import os
from urllib.parse import urlparse

from starlette.middleware.cors import CORSMiddleware

from .authenticated_server import build_oidc_authenticated_server_from_env


def create_app():
    """Build the OIDC-protected MCP ASGI application from environment settings."""
    server = build_oidc_authenticated_server_from_env()
    app = server.streamable_http_app()
    raw_origins = os.getenv("MEHR_ALLOWED_ORIGINS", "").strip()
    if not raw_origins:
        return app
    origins = [origin.strip() for origin in raw_origins.split(",") if origin.strip()]
    if not origins or "*" in origins:
        raise ValueError("MEHR_ALLOWED_ORIGINS must contain explicit origins; wildcards are forbidden")
    normalized_origins = []
    for origin in origins:
        parsed = urlparse(origin)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("MEHR_ALLOWED_ORIGINS entries must be HTTPS origins without credentials, paths, query, or fragments")
        normalized_origins.append(f"https://{parsed.netloc}")
    origins = list(dict.fromkeys(normalized_origins))
    return CORSMiddleware(
        app,
        allow_origins=origins,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "Mcp-Session-Id",
            "Mcp-Protocol-Version",
            "Last-Event-ID",
        ],
        expose_headers=["Mcp-Session-Id", "Mcp-Protocol-Version"],
        allow_credentials=False,
        max_age=600,
    )


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
