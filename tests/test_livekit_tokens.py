"""Tests for server-side LiveKit access-token issuance."""

import jwt
import pytest

from mehr_ai_studio.realtime.livekit_tokens import LiveKitTokenIssuer


def test_issues_room_scoped_short_lived_token_with_explicit_grants():
    issuer = LiveKitTokenIssuer("test-api-key", "test-api-secret", ttl_seconds=180)

    token = issuer.issue(
        room="session_123",
        identity="participant_456",
        can_publish=False,
        can_subscribe=True,
        can_publish_data=False,
    )
    claims = jwt.decode(
        token,
        "test-api-secret",
        algorithms=["HS256"],
        options={"verify_exp": False, "verify_nbf": False},
    )

    assert claims["iss"] == "test-api-key"
    assert claims["sub"] == "participant_456"
    assert claims["exp"] - claims["iat"] == 180
    assert claims["nbf"] == claims["iat"]
    assert claims["video"] == {
        "roomJoin": True,
        "room": "session_123",
        "canPublish": False,
        "canSubscribe": True,
        "canPublishData": False,
    }


@pytest.mark.parametrize(
    ("api_key", "api_secret", "ttl_seconds"),
    [
        ("", "secret", 300),
        ("key", "", 300),
        ("key", "secret", 59),
        ("key", "secret", 601),
        ("key", "secret", True),
    ],
)
def test_rejects_missing_credentials_and_unsafe_ttl(api_key, api_secret, ttl_seconds):
    with pytest.raises(ValueError):
        LiveKitTokenIssuer(api_key, api_secret, ttl_seconds)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("room", ""),
        ("room", "room with spaces"),
        ("room", "private@example.com"),
        ("identity", ""),
        ("identity", "person name"),
        ("identity", "person@example.com"),
        ("identity", "x" * 129),
    ],
)
def test_rejects_invalid_or_personal_identifier_shapes(field, value):
    issuer = LiveKitTokenIssuer("key", "secret")
    args = {"room": "room_123", "identity": "user_123"}
    args[field] = value

    with pytest.raises(ValueError):
        issuer.issue(**args)


@pytest.mark.parametrize(
    ("grant", "value"),
    [
        ("can_publish", 1),
        ("can_subscribe", "true"),
        ("can_publish_data", None),
    ],
)
def test_rejects_non_boolean_grants(grant, value):
    issuer = LiveKitTokenIssuer("key", "secret")
    grants = {
        "can_publish": True,
        "can_subscribe": True,
        "can_publish_data": False,
    }
    grants[grant] = value

    with pytest.raises(ValueError, match=grant):
        issuer.issue(room="room_123", identity="user_123", **grants)


def test_loads_credentials_only_from_server_environment(monkeypatch):
    monkeypatch.setenv("LIVEKIT_API_KEY", "server-key")
    monkeypatch.setenv("LIVEKIT_API_SECRET", "server-secret")

    issuer = LiveKitTokenIssuer.from_env()

    assert issuer.api_key == "server-key"
    assert issuer.api_secret == "server-secret"
