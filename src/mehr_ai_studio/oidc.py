"""Standards-based OIDC JWT access-token verification using a trusted JWKS."""

import asyncio
import math
import time
from typing import Any
from urllib.parse import urlparse

import jwt
from jwt import PyJWKClient
from mcp.server.auth.provider import AccessToken, TokenVerifier

from .store import validate_tenant_id


class OIDCConfigurationError(ValueError):
    """Raised when OIDC verifier configuration is incomplete or unsafe."""


class OIDCJWTTokenVerifier(TokenVerifier):
    """Verify signed OIDC JWT access tokens against a pinned issuer and audience.

    RS256 is intentionally the only accepted algorithm. JWKS keys are cached by
    PyJWKClient; network/key lookup runs in a worker thread to avoid blocking
    the event loop.
    """

    def __init__(
        self,
        *,
        issuer_url: str,
        jwks_url: str,
        audience: str,
        resource_server_url: str,
        required_scopes: list[str],
        tenant_claim: str = "tenant_id",
        jwks_cache_seconds: int = 300,
        leeway_seconds: int = 0,
    ) -> None:
        for name, value in (
            ("issuer_url", issuer_url),
            ("jwks_url", jwks_url),
            ("resource_server_url", resource_server_url),
        ):
            parsed = urlparse(value)
            if (
                parsed.scheme != "https"
                or not parsed.hostname
                or parsed.username is not None
                or parsed.password is not None
                or parsed.query
                or parsed.fragment
            ):
                raise OIDCConfigurationError(
                    f"{name} must be an absolute HTTPS URL without credentials, query, or fragment"
                )
        if not isinstance(audience, str) or not audience.strip():
            raise OIDCConfigurationError("audience must be a non-empty string")
        if (
            not isinstance(required_scopes, list)
            or not required_scopes
            or any(not isinstance(scope, str) or not scope.strip() for scope in required_scopes)
        ):
            raise OIDCConfigurationError("At least one non-empty required scope is mandatory")
        if not isinstance(tenant_claim, str) or not tenant_claim.strip():
            raise OIDCConfigurationError("tenant_claim must be a non-empty string")
        if (
            isinstance(jwks_cache_seconds, bool)
            or not isinstance(jwks_cache_seconds, int)
            or isinstance(leeway_seconds, bool)
            or not isinstance(leeway_seconds, int)
            or jwks_cache_seconds < 1
            or leeway_seconds < 0
        ):
            raise OIDCConfigurationError("JWKS cache must be positive and leeway non-negative")

        self.issuer_url = issuer_url
        self.jwks_url = jwks_url
        self.audience = audience
        self.resource_server_url = resource_server_url.rstrip("/")
        self.required_scopes = frozenset(required_scopes)
        self.tenant_claim = tenant_claim
        self.leeway_seconds = leeway_seconds
        self._jwks = PyJWKClient(
            jwks_url,
            cache_jwk_set=True,
            lifespan=jwks_cache_seconds,
            timeout=5,
        )

    async def verify_token(self, token: str) -> AccessToken | None:
        if not isinstance(token, str) or not token or len(token) > 16384:
            return None
        try:
            signing_key = await asyncio.to_thread(
                self._jwks.get_signing_key_from_jwt, token
            )
            claims: dict[str, Any] = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                audience=self.audience,
                issuer=self.issuer_url,
                leeway=self.leeway_seconds,
                options={
                    "require": ["exp", "iat", "iss", "aud", "sub"],
                    "verify_signature": True,
                    "verify_exp": True,
                    "verify_iat": True,
                    "verify_nbf": True,
                    "verify_iss": True,
                    "verify_aud": True,
                },
            )
            subject = claims.get("sub")
            tenant_id = claims.get(self.tenant_claim)
            client_id = claims.get("azp") or claims.get("client_id")
            raw_scopes = claims.get("scope", claims.get("scp", []))
            if isinstance(raw_scopes, str):
                scopes = raw_scopes.split()
            elif isinstance(raw_scopes, list) and all(
                isinstance(scope, str) for scope in raw_scopes
            ):
                scopes = raw_scopes
            else:
                return None
            if (
                not isinstance(subject, str)
                or not subject.strip()
                or not isinstance(tenant_id, str)
                or not tenant_id.strip()
                or not isinstance(client_id, str)
                or not client_id.strip()
                or not self.required_scopes.issubset(scopes)
            ):
                return None
            # Reject non-finite or implausible timestamps before SDK handoff.
            expires_at = claims.get("exp")
            issued_at = claims.get("iat")
            if (
                isinstance(expires_at, bool)
                or isinstance(issued_at, bool)
                or not isinstance(expires_at, (int, float))
                or not isinstance(issued_at, (int, float))
                or not math.isfinite(expires_at)
                or not math.isfinite(issued_at)
                or expires_at <= time.time()
                or issued_at > time.time() + self.leeway_seconds
                or expires_at - issued_at > 86400
            ):
                return None
            try:
                trusted_tenant_id = validate_tenant_id(tenant_id)
            except (TypeError, ValueError):
                return None
            # Normalize a configured tenant claim name for the request context.
            trusted_claims = dict(claims)
            trusted_claims["tenant_id"] = trusted_tenant_id
            return AccessToken(
                token=token,
                client_id=client_id,
                scopes=scopes,
                expires_at=int(expires_at),
                resource=self.resource_server_url,
                subject=subject,
                claims=trusted_claims,
            )
        except (jwt.PyJWTError, ValueError, TypeError, KeyError, OSError, TimeoutError, OverflowError):
            return None
