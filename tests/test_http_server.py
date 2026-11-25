"""Tests for the opt-in authenticated HTTP entry point."""

import pytest

from mehr_ai_studio import http_server


def test_create_app_uses_oidc_authenticated_mcp_factory(monkeypatch):
    marker = object()

    class FakeServer:
        def streamable_http_app(self):
            return marker

    monkeypatch.setattr(
        http_server,
        "build_oidc_authenticated_server_from_env",
        lambda: FakeServer(),
    )
    assert http_server.create_app() is marker


def test_http_main_defaults_to_loopback_and_disables_proxy_header_trust(
    monkeypatch,
):
    import uvicorn

    calls = {}
    monkeypatch.setattr(http_server, "create_app", lambda: "asgi-app")
    monkeypatch.setattr(uvicorn, "run", lambda app, **kwargs: calls.update(
        {"app": app, **kwargs}
    ))
    monkeypatch.delenv("MEHR_HTTP_HOST", raising=False)
    monkeypatch.delenv("MEHR_HTTP_PORT", raising=False)

    http_server.main()

    assert calls == {
        "app": "asgi-app",
        "host": "127.0.0.1",
        "port": 8000,
        "proxy_headers": False,
    }


def test_http_main_rejects_invalid_port_before_starting_server(monkeypatch):
    monkeypatch.setenv("MEHR_HTTP_PORT", "not-a-port")
    with pytest.raises(ValueError, match="MEHR_HTTP_PORT"):
        http_server.main()


def test_create_app_wraps_mcp_with_exact_cors_allowlist(monkeypatch):
    from starlette.middleware.cors import CORSMiddleware

    class FakeServer:
        def streamable_http_app(self):
            return "asgi-app"

    monkeypatch.setattr(
        http_server,
        "build_oidc_authenticated_server_from_env",
        lambda: FakeServer(),
    )
    monkeypatch.setenv(
        "MEHR_ALLOWED_ORIGINS",
        "https://studio.example.test, https://preview.example.test",
    )

    app = http_server.create_app()

    assert isinstance(app, CORSMiddleware)
    assert app.allow_origins == [
        "https://studio.example.test",
        "https://preview.example.test",
    ]
    assert app.allow_credentials is False
    assert "Authorization" in app.allow_headers
    assert "Mcp-Session-Id" in app.allow_headers


def test_create_app_rejects_wildcard_cors_origin(monkeypatch):
    class FakeServer:
        def streamable_http_app(self):
            return "asgi-app"

    monkeypatch.setattr(
        http_server,
        "build_oidc_authenticated_server_from_env",
        lambda: FakeServer(),
    )
    monkeypatch.setenv("MEHR_ALLOWED_ORIGINS", "*")

    with pytest.raises(ValueError, match="wildcards are forbidden"):
        http_server.create_app()
