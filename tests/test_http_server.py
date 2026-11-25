"""Tests for the opt-in authenticated HTTP entry point."""

from types import SimpleNamespace

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
