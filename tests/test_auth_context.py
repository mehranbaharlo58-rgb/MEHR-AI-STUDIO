"""Tests for trusted request identity to tenant mapping."""

from types import SimpleNamespace

import pytest

from mehr_ai_studio import auth_context


def test_verified_tenant_claim_is_normalized():
    token = SimpleNamespace(claims={"tenant_id": "  customer-a  "})
    assert auth_context.tenant_id_from_access_token(token) == "customer-a"


@pytest.mark.parametrize(
    "token",
    [
        None,
        SimpleNamespace(claims=None),
        SimpleNamespace(claims=[]),
        SimpleNamespace(claims={"sub": "user-a"}),
        SimpleNamespace(claims={"tenant_id": ""}),
        SimpleNamespace(claims={"tenant_id": "x" * 129}),
        SimpleNamespace(claims={"tenant_id": 123}),
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
    token = SimpleNamespace(claims={"tenant_id": "tenant-b"})
    monkeypatch.setattr(auth_context, "get_access_token", lambda: token)
    assert auth_context.current_request_tenant_id() == "tenant-b"
