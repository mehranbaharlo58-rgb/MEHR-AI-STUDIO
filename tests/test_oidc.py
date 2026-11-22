"""Tests for standards-based OIDC JWT verification."""

import asyncio
import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt import PyJWK
from mcp.server.auth.provider import AccessToken

from mehr_ai_studio.oidc import OIDCConfigurationError, OIDCJWTTokenVerifier

ISSUER = "https://issuer.example.test/"
AUDIENCE = "mehr-ai-studio-api"
RESOURCE = "https://studio.example.test/mcp"
TENANT = "tenant-customer-a"


class FakeJWKClient:
    def __init__(self, signing_key):
        self.signing_key = signing_key

    def get_signing_key_from_jwt(self, token):
        return self.signing_key


@pytest.fixture
def rsa_keys():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_jwk = PyJWK.from_dict(
        jwt.algorithms.RSAAlgorithm.to_jwk(
            private_key.public_key(), as_dict=True
        )
        | {"kid": "test-key", "alg": "RS256", "use": "sig"}
    )
    return private_key, public_jwk


@pytest.fixture
def verifier(rsa_keys):
    _, public_jwk = rsa_keys
    instance = OIDCJWTTokenVerifier(
        issuer_url=ISSUER,
        jwks_url="https://issuer.example.test/.well-known/jwks.json",
        audience=AUDIENCE,
        resource_server_url=RESOURCE,
        required_scopes=["studio:access"],
    )
    instance._jwks = FakeJWKClient(public_jwk)
    return instance


def make_token(private_key, **overrides):
    now = int(time.time())
    claims = {
        "iss": ISSUER,
        "aud": AUDIENCE,
        "sub": "user-123",
        "azp": "studio-client",
        "tenant_id": TENANT,
        "scope": "studio:access profile",
        "iat": now,
        "exp": now + 300,
    }
    claims.update(overrides)
    return jwt.encode(
        claims, private_key, algorithm="RS256", headers={"kid": "test-key"}
    )


def test_valid_signed_token_becomes_sdk_access_token(verifier, rsa_keys):
    private_key, _ = rsa_keys
    result = asyncio.run(verifier.verify_token(make_token(private_key)))
    assert isinstance(result, AccessToken)
    assert result.subject == "user-123"
    assert result.client_id == "studio-client"
    assert result.resource == RESOURCE
    assert result.claims["tenant_id"] == TENANT
    assert "studio:access" in result.scopes


@pytest.mark.parametrize(
    "claims",
    [
        {"iss": "https://attacker.example.test/"},
        {"aud": "other-api"},
        {"exp": int(time.time()) - 60},
        {"sub": ""},
        {"tenant_id": ""},
        {"scope": "profile"},
        {"azp": ""},
    ],
)
def test_rejects_invalid_claims(verifier, rsa_keys, claims):
    private_key, _ = rsa_keys
    assert asyncio.run(verifier.verify_token(make_token(private_key, **claims))) is None


def test_rejects_wrong_signature(verifier):
    other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    token = make_token(other_key)
    assert asyncio.run(verifier.verify_token(token)) is None


def test_rejects_non_jwt(verifier):
    assert asyncio.run(verifier.verify_token("not-a-jwt")) is None


def test_requires_https_and_scopes():
    with pytest.raises(OIDCConfigurationError):
        OIDCJWTTokenVerifier(
            issuer_url="http://issuer.example.test",
            jwks_url="https://issuer.example.test/jwks",
            audience=AUDIENCE,
            resource_server_url=RESOURCE,
            required_scopes=["studio:access"],
        )
    with pytest.raises(OIDCConfigurationError):
        OIDCJWTTokenVerifier(
            issuer_url=ISSUER,
            jwks_url="https://issuer.example.test/jwks",
            audience=AUDIENCE,
            resource_server_url=RESOURCE,
            required_scopes=[],
        )
