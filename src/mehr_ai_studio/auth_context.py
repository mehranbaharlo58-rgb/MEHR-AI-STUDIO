"""Resolve tenant scope only from an SDK-verified request token."""

from collections.abc import Mapping
from typing import Any

from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import AccessToken

from .store import validate_tenant_id


class AuthenticationRequired(PermissionError):
    """Raised when a protected operation has no verified identity."""


def tenant_id_from_access_token(access_token: AccessToken | None) -> str:
    """Return the trusted tenant claim from an SDK-verified access token.

    The token verifier must validate signature/introspection, issuer, audience,
    expiry, and scopes before the SDK creates this AccessToken. Never pass a
    caller-supplied tool argument to this function.
    """
    if access_token is None:
        raise AuthenticationRequired("A verified access token is required")

    subject: Any = access_token.subject
    if not isinstance(subject, str) or not subject.strip():
        raise AuthenticationRequired("The verified token has no subject")

    claims: Any = access_token.claims
    if not isinstance(claims, Mapping):
        raise AuthenticationRequired("The verified token has no trusted claims")

    tenant_id = claims.get("tenant_id")
    if not isinstance(tenant_id, str):
        raise AuthenticationRequired("The verified token has no tenant_id claim")

    try:
        return validate_tenant_id(tenant_id)
    except (TypeError, ValueError) as exc:
        raise AuthenticationRequired("The verified tenant_id claim is invalid") from exc


def current_request_tenant_id() -> str:
    """Resolve the current HTTP request tenant; fail closed outside auth context."""
    return tenant_id_from_access_token(get_access_token())
