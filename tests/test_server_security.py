"""Security regression tests for the local-only MCP server boundary."""

import inspect

import pytest

from mehr_ai_studio import server


@pytest.mark.parametrize(
    "tool_name",
    [
        "save_project_memory",
        "read_project_memory",
        "record_content_feedback",
        "get_feedback_insights",
        "run_content_workflow",
    ],
)
def test_public_mcp_tools_do_not_accept_caller_supplied_tenant_id(tool_name):
    """A client must not be able to choose another tenant through tool arguments."""
    tool = getattr(server, tool_name)
    assert "tenant_id" not in inspect.signature(tool).parameters


def test_server_entry_point_uses_local_stdio_transport(monkeypatch):
    """The current server must not silently become a network service."""
    calls = []

    def fake_run(**kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(server.app, "run", fake_run)
    server.main()

    assert calls == [{"transport": "stdio"}]
