"""Server-side LiveKit access-token issuance with least-privilege room grants."""

import re
import time
from dataclasses import dataclass

import jwt


_IDENTIFIER_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}\\Z")
_MIN_TTL_SECONDS = 60
_MAX_TTL_SECONDS = 600


@dataclass(frozen=True, slots=True)
class LiveKitTokenIssuer:
    """Sign short-lived participant tokens; keep API credentials server-side."""

    api_key: str
    api_secret: str
    ttl_seconds: int = 300

    def __post_init__(self) -> None:
        if not isinstance(self.api_key, str) or not self.api_key.strip():
            raise ValueError("LiveKit API key is required")
        if not isinstance(self.api_secret, str) or not self.api_secret.strip():
            raise ValueError("LiveKit API secret is required")
        if (
            isinstance(self.ttl_seconds, bool)
            or not isinstance(self.ttl_seconds, int)
            or not _MIN_TTL_SECONDS <= self.ttl_seconds <= _MAX_TTL_SECONDS
        ):
            raise ValueError(
                f"LiveKit token TTL must be between {_MIN_TTL_SECONDS} "
                f"and {_MAX_TTL_SECONDS} seconds"
            )

    @classmethod
    def from_env(cls) -> "LiveKitTokenIssuer":
        """Load credentials only from the server process environment."""
        import os

        return cls(
            api_key=os.getenv("LIVEKIT_API_KEY", ""),
            api_secret=os.getenv("LIVEKIT_API_SECRET", ""),
        )

    def issue(
        self,
        *,
        room: str,
        identity: str,
        can_publish: bool = True,
        can_subscribe: bool = True,
        can_publish_data: bool = False,
    ) -> str:
        """Issue a room-scoped token with every publish grant set explicitly."""
        for name, value in (("room", room), ("identity", identity)):
            if not isinstance(value, str) or not _IDENTIFIER_RE.fullmatch(value):
                raise ValueError(
                    f"{name} must be 1-128 ASCII letters, digits, '_' or '-' "
                    "and start with a letter or digit"
                )
        for name, value in (
            ("can_publish", can_publish),
            ("can_subscribe", can_subscribe),
            ("can_publish_data", can_publish_data),
        ):
            if not isinstance(value, bool):
                raise TypeError(f"{name} must be a boolean")

        now = int(time.time())
        payload = {
            "iss": self.api_key,
            "sub": identity,
            "nbf": now,
            "iat": now,
            "exp": now + self.ttl_seconds,
            "video": {
                "roomJoin": True,
                "room": room,
                "canPublish": can_publish,
                "canSubscribe": can_subscribe,
                "canPublishData": can_publish_data,
            },
        }
        return jwt.encode(payload, self.api_secret, algorithm="HS256")
