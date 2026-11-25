"""Provider-neutral contracts and fail-closed capability negotiation for MEHR Live."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class LiveMode(StrEnum):
    VOICE = "voice"
    VOICE_VISION = "voice_vision"
    VOICE_VISION_AVATAR = "voice_vision_avatar"


class ProviderCapabilities(BaseModel):
    """Capabilities explicitly declared by a provider adapter."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    voice_input: bool = False
    voice_output: bool = False
    image_input: bool = False
    continuous_video_input: bool = False
    interruption: bool = False
    avatar_video_output: bool = False
    synchronized_avatar_audio: bool = False


class LiveConsent(BaseModel):
    """Per-session user consent; all capture permissions default to off."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    microphone: bool = False
    camera: bool = False
    avatar: bool = False


class LiveSessionRequest(BaseModel):
    """A requested mode and its explicit consent, not an identity assertion."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    mode: LiveMode
    consent: LiveConsent
    max_duration_seconds: int = Field(default=600, ge=30, le=3600)
    max_image_frames_per_minute: int = Field(default=6, ge=0, le=30)

    @model_validator(mode="after")
    def validate_consent_and_limits(self) -> "LiveSessionRequest":
        if not self.consent.microphone:
            raise ValueError("microphone consent is required for a live session")
        if self.mode in {LiveMode.VOICE_VISION, LiveMode.VOICE_VISION_AVATAR}:
            if not self.consent.camera:
                raise ValueError("camera consent is required for the selected mode")
            if self.max_image_frames_per_minute < 1:
                raise ValueError("vision mode requires a positive frame sampling limit")
        elif self.consent.camera or self.max_image_frames_per_minute != 6:
            raise ValueError("voice-only mode must not enable camera sampling")
        if self.mode is LiveMode.VOICE_VISION_AVATAR and not self.consent.avatar:
            raise ValueError("avatar consent is required for avatar mode")
        if self.mode is not LiveMode.VOICE_VISION_AVATAR and self.consent.avatar:
            raise ValueError("avatar consent is only valid in avatar mode")
        return self


def supports_mode(capabilities: ProviderCapabilities, mode: LiveMode) -> bool:
    """Return true only when every capability required by a mode is explicit."""
    if not (capabilities.voice_input and capabilities.voice_output):
        return False
    if mode is LiveMode.VOICE:
        return True
    if not (capabilities.image_input and capabilities.interruption):
        return False
    if mode is LiveMode.VOICE_VISION:
        return True
    return (
        capabilities.avatar_video_output
        and capabilities.synchronized_avatar_audio
    )


def eligible_providers(
    providers: dict[str, ProviderCapabilities], mode: LiveMode
) -> list[str]:
    """Return deterministic provider IDs that satisfy the complete requested mode."""
    return sorted(
        provider_id
        for provider_id, capabilities in providers.items()
        if provider_id.strip() and supports_mode(capabilities, mode)
    )
