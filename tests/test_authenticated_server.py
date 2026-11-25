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
        read_workflow_run=lambda run_id, tenant_id: {
            "run_id": run_id, "tenant_id": tenant_id
        },
        list_workflow_runs=lambda tenant_id, limit: [
            {"tenant_id": tenant_id, "limit": limit}
        ],
    )
    monkeypatch.setattr(
        authenticated_server, "current_request_tenant_id", lambda: "tenant-from-token"
    )
    monkeypatch.setattr(
        authenticated_server,
        "execute_resume_content_workflow",
        lambda store, run_id, tenant_id: {
            "run_id": run_id, "tenant_id": tenant_id
        },
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
    assert app.tools["read_workflow_run"]("run-1")["tenant_id"] == "tenant-from-token"
    assert app.tools["list_workflow_runs"](5)["runs"][0]["tenant_id"] == "tenant-from-token"
    assert app.tools["resume_content_workflow"]("run-1")["tenant_id"] == "tenant-from-token"


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
        "read_workflow_run",
        "list_workflow_runs",
        "resume_content_workflow",
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
        validate_token_resource=True,
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


@pytest.mark.parametrize(
    "settings, message",
    [
        (
            SimpleNamespace(
                issuer_url="https://user:password@identity.example.test/",
                resource_server_url="https://studio.example.test/mcp",
                required_scopes=["studio:access"],
            ),
            "issuer_url",
        ),
        (
            SimpleNamespace(
                issuer_url="https://identity.example.test/",
                resource_server_url="https://",
                required_scopes=["studio:access"],
            ),
            "resource_server_url",
        ),
        (
            SimpleNamespace(
                issuer_url="https://identity.example.test/",
                resource_server_url="https://studio.example.test/mcp",
                required_scopes=["   "],
            ),
            "scope",
        ),
        (
            SimpleNamespace(
                issuer_url="https://identity.example.test/",
                resource_server_url="https://studio.example.test/mcp",
                required_scopes=[None],
            ),
            "scope",
        ),
    ],
)
def test_authenticated_factory_rejects_unsafe_auth_configuration(settings, message):
    with pytest.raises(ValueError, match=message):
        authenticated_server._validate_auth_configuration(FakeVerifier(), settings)



def test_authenticated_tool_handlers_enforce_sqlite_tenant_partitioning(
    monkeypatch, tmp_path
):
    """Exercise the real SQLite tenant boundary through authenticated tool handlers."""
    from mehr_ai_studio.store import StudioStore

    monkeypatch.setattr(authenticated_server, "FastMCP", FakeMCP)
    active_tenant = {"id": "tenant-alpha"}
    monkeypatch.setattr(
        authenticated_server,
        "current_request_tenant_id",
        lambda: active_tenant["id"],
    )
    store = StudioStore(tmp_path / "tenant-isolation.sqlite3")
    app = authenticated_server.build_authenticated_server(
        token_verifier=FakeVerifier(),
        auth_settings=valid_auth_settings(),
        store=store,
    )

    alpha_save = app.tools["save_project_memory"]("private", "alpha-secret")
    assert alpha_save["tenant_id"] == "tenant-alpha"
    assert app.tools["read_project_memory"]("private")["value"] == "alpha-secret"

    active_tenant["id"] = "tenant-beta"
    assert app.tools["read_project_memory"]("private") == {
        "found": False,
        "key": "private",
    }
    beta_save = app.tools["save_project_memory"]("private", "beta-secret")
    assert beta_save["tenant_id"] == "tenant-beta"
    assert app.tools["read_project_memory"]("private")["value"] == "beta-secret"

    active_tenant["id"] = "tenant-alpha"
    assert app.tools["read_project_memory"]("private")["value"] == "alpha-secret"
    assert store.feedback_insights(tenant_id="tenant-alpha")["feedback_count"] == 0
    assert store.feedback_insights(tenant_id="tenant-beta")["feedback_count"] == 0


def test_authenticated_ai_registry_tools_are_tenant_scoped(monkeypatch, tmp_path):
    """AI registry reads/writes must follow the verified tenant claim."""
    import inspect

    from mehr_ai_studio.ai_registry_store import AIRegistryStore

    monkeypatch.setattr(authenticated_server, "FastMCP", FakeMCP)
    monkeypatch.setattr(
        authenticated_server,
        "settings",
        SimpleNamespace(
            database_path=tmp_path / "tenant-ai-registry.sqlite3",
            provider_base_url=None,
            provider_api_key=None,
            request_timeout=1,
        ),
    )
    active_tenant = {"id": "tenant-alpha"}
    monkeypatch.setattr(
        authenticated_server,
        "current_request_tenant_id",
        lambda: active_tenant["id"],
    )
    app = authenticated_server.build_authenticated_server(
        token_verifier=FakeVerifier(),
        auth_settings=valid_auth_settings(),
    )

    model = {
        "id": "local.test",
        "name": "Local Test",
        "provider": "Local Runtime",
        "category": "reasoning",
        "capabilities": ["reasoning"],
        "task_tags": ["analysis"],
        "access_mode": "local_runtime",
        "availability": "local",
        "status": "configured",
        "model_id": "test-model",
        "endpoint": "http://127.0.0.1:11434/v1",
        "auth_required": False,
    }
    assert app.tools["register_ai_model"](model)["saved"] is True
    alpha = app.tools["list_ai_models"]()
    assert alpha["counts"]["configured"] == 1
    assert alpha["models"][0]["id"] == "local.test"
    assert app.tools["match_ai_models"]("analysis")["matches"][0]["model_id"] == "local.test"

    active_tenant["id"] = "tenant-beta"
    beta = app.tools["list_ai_models"]()
    assert beta["counts"]["total"] == 0
    assert beta["models"] == []
    assert app.tools["match_ai_models"]("analysis")["matches"] == []

    active_tenant["id"] = "tenant-alpha"
    assert app.tools["list_ai_models"]()["counts"]["total"] == 1

    for name in (
        "register_ai_model",
        "list_ai_models",
        "match_ai_models",
        "seed_ai_catalog",
        "execute_ai_task",
        "test_ai_connector",
    ):
        assert "tenant_id" not in inspect.signature(app.tools[name]).parameters

    # A separately constructed tenant store cannot see the caller's records.
    assert AIRegistryStore(
        tmp_path / "tenant-ai-registry.sqlite3", "tenant-beta"
    ).list() == []
