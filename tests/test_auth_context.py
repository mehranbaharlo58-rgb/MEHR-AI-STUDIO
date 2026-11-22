"""Tests for trusted request identity to tenant mapping."""

from types import SimpleNamespace

import pytest

from mehr_ai_studio import auth_context


def test_verified_tenant_claim_is_normalized():
    token = SimpleNamespace(subject="user-a", claims={"tenant_id": "  customer-a  "})
    assert auth_context.tenant_id_from_access_token(token) == "customer-a"


@pytest.mark.parametrize(
    "token",
    [
        None,
        SimpleNamespace(subject="user-a", claims=None),
        SimpleNamespace(subject="user-a", claims=[]),
        SimpleNamespace(subject="user-a", claims={"sub": "user-a"}),
        SimpleNamespace(subject="user-a", claims={"tenant_id": ""}),
        SimpleNamespace(subject="user-a", claims={"tenant_id": "x" * 129}),
        SimpleNamespace(subject="user-a", claims={"tenant_id": 123}),
    ],
)
def test_missing_or_invalid_tenant_claim_fails_closed(token):
    with pytest.raises(auth_context.AuthenticationRequired):
        auth_context.tenant_id_from_access_token(token)


def test_current_request_tenant_requires_sdk_auth_context(monkeypatch):
    monkeypatch.setattr(auth_context, "get_access_token", lambda: None)
    with pytest.raises(auth_context.AuthenticationRequired):
        auth_context.current_request_tenant_id()


def test_current_request_tenant_uses_verified_token_claim(monkeypatch):
    token = SimpleNamespace(subject="user-b", claims={"tenant_id": "tenant-b"})
    monkeypatch.setattr(auth_context, "get_access_token", lambda: token)
    assert auth_context.current_request_tenant_id() == "tenant-b"


@pytest.mark.parametrize("subject", [None, "", "   ", 123])
def test_missing_or_invalid_subject_fails_closed(subject):
    token = SimpleNamespace(subject=subject, claims={"tenant_id": "tenant-a"})
    with pytest.raises(auth_context.AuthenticationRequired):
        auth_context.tenant_id_from_access_token(token)


def test_sdk_access_token_subject_and_claims_are_supported():
    from mcp.server.auth.provider import AccessToken

    token = AccessToken(
        token="verified-test-token",
        client_id="test-client",
        scopes=["studio:access"],
        subject="user-c",
        claims={"tenant_id": "tenant-c"},
    )
    assert auth_context.tenant_id_from_access_token(token) == "tenant-c"
