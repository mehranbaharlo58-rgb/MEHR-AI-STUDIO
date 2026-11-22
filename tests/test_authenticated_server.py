"""Tests for the opt-in authenticated server factory."""

from types import SimpleNamespace

import pytest

from mehr_ai_studio import authenticated_server


class FakeMCP:
    def __init__(self, name, **kwargs):
        self.name = name
        self.options = kwargs
        self.tools = {}

    def tool(self):
        def register(function):
            self.tools[function.__name__] = function
            return function
        return register


class FakeVerifier:
    async def verify_token(self, token):
        return None


def valid_auth_settings():
    return SimpleNamespace(
        issuer_url="https://identity.example.test/",
        resource_server_url="https://studio.example.test/mcp",
        required_scopes=["studio:access"],
    )


def test_authenticated_factory_requires_https_issuer_and_resource():
    with pytest.raises(ValueError, match="issuer_url"):
        authenticated_server._validate_auth_configuration(
            FakeVerifier(),
            SimpleNamespace(
                issuer_url="http://identity.example.test/",
                resource_server_url="https://studio.example.test/mcp",
                required_scopes=["studio:access"],
            ),
        )


def test_authenticated_factory_requires_scopes():
    with pytest.raises(ValueError, match="scope"):
        authenticated_server._validate_auth_configuration(
            FakeVerifier(),
            SimpleNamespace(
                issuer_url="https://identity.example.test/",
                resource_server_url="https://studio.example.test/mcp",
                required_scopes=[],
            ),
        )


def test_authenticated_factory_injects_verifier_and_registers_tenant_tools(monkeypatch):
    monkeypatch.setattr(authenticated_server, "FastMCP", FakeMCP)
    store = SimpleNamespace(
        save_memory=lambda key, value, tenant_id: {
            "key": key, "value": value, "tenant_id": tenant_id
        },
        read_memory=lambda key, tenant_id: {
            "key": key, "value": "saved", "tenant_id": tenant_id
        },
        record_feedback=lambda item_type, rating, note, tenant_id: {
            "tenant_id": tenant_id, "rating": rating
        },
        feedback_insights=lambda tenant_id: {"tenant_id": tenant_id},
    )
    monkeypatch.setattr(
        authenticated_server, "current_request_tenant_id", lambda: "tenant-from-token"
    )

    app = authenticated_server.build_authenticated_server(
        token_verifier=FakeVerifier(),
        auth_settings=valid_auth_settings(),
        store=store,
    )

    assert app.options["token_verifier"].__class__ is FakeVerifier
    assert app.options["auth"].required_scopes == ["studio:access"]
    assert app.tools["save_project_memory"]("k", "v")["tenant_id"] == "tenant-from-token"
    assert app.tools["read_project_memory"]("k")["tenant_id"] == "tenant-from-token"
    assert app.tools["record_content_feedback"]("draft", 5)["tenant_id"] == "tenant-from-token"
    assert app.tools["get_feedback_insights"]()["tenant_id"] == "tenant-from-token"


def test_authenticated_tool_signatures_never_accept_tenant_id(monkeypatch):
    import inspect

    monkeypatch.setattr(authenticated_server, "FastMCP", FakeMCP)
    app = authenticated_server.build_authenticated_server(
        token_verifier=FakeVerifier(),
        auth_settings=valid_auth_settings(),
        store=SimpleNamespace(),
    )
    for name in (
        "save_project_memory",
        "read_project_memory",
        "record_content_feedback",
        "get_feedback_insights",
        "run_content_workflow",
    ):
        assert "tenant_id" not in inspect.signature(app.tools[name]).parameters


def test_streamable_http_rejects_missing_and_invalid_bearer_tokens(monkeypatch):
    import asyncio

    import httpx
    from mcp.server.auth.settings import AuthSettings

    from mehr_ai_studio.authenticated_server import build_authenticated_server

    verifier = FakeVerifier()
    auth = AuthSettings(
        issuer_url="https://identity.example.test/",
        resource_server_url="https://studio.example.test/mcp",
        required_scopes=["studio:access"],
    )
    mcp = build_authenticated_server(
        token_verifier=verifier,
        auth_settings=auth,
    )
    asgi_app = mcp.streamable_http_app()

    async def exercise():
        async with mcp.session_manager.run(), httpx.AsyncClient(
            transport=httpx.ASGITransport(app=asgi_app),
            base_url="http://127.0.0.1",
        ) as client:
            missing = await client.get("/mcp")
            invalid = await client.get(
                "/mcp", headers={"Authorization": "Bearer invalid-token"}
            )
            return missing.status_code, invalid.status_code

    assert asyncio.run(exercise()) == (401, 401)
