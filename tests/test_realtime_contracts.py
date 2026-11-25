"""Tests for MEHR Live provider-neutral session contracts."""

import pytest
from pydantic import ValidationError

from mehr_ai_studio.realtime.contracts import (
    LiveConsent,
    LiveMode,
    LiveSessionRequest,
    ProviderCapabilities,
    eligible_providers,
    supports_mode,
)


def test_microphone_consent_is_required():
    with pytest.raises(ValidationError, match="microphone consent"):
        LiveSessionRequest(mode=LiveMode.VOICE, consent=LiveConsent())


def test_vision_requires_camera_consent_and_bounded_sampling():
    with pytest.raises(ValidationError, match="camera consent"):
        LiveSessionRequest(
            mode=LiveMode.VOICE_VISION,
            consent=LiveConsent(microphone=True),
        )
    with pytest.raises(ValidationError, match="positive frame sampling"):
        LiveSessionRequest(
            mode=LiveMode.VOICE_VISION,
            consent=LiveConsent(microphone=True, camera=True),
            max_image_frames_per_minute=0,
        )


def test_voice_only_rejects_camera_capture():
    with pytest.raises(ValidationError, match="voice-only"):
        LiveSessionRequest(
            mode=LiveMode.VOICE,
            consent=LiveConsent(microphone=True, camera=True),
        )


def test_avatar_mode_requires_separate_explicit_consent():
    with pytest.raises(ValidationError, match="avatar consent"):
        LiveSessionRequest(
            mode=LiveMode.VOICE_VISION_AVATAR,
            consent=LiveConsent(microphone=True, camera=True),
        )


def test_avatar_requires_video_and_audio_synchronization_capabilities():
    capabilities = ProviderCapabilities(
        voice_input=True,
        voice_output=True,
        image_input=True,
        interruption=True,
        avatar_video_output=True,
    )
    assert supports_mode(capabilities, LiveMode.VOICE_VISION)
    assert not supports_mode(capabilities, LiveMode.VOICE_VISION_AVATAR)


def test_provider_selection_is_complete_and_deterministic():
    providers = {
        "voice": ProviderCapabilities(voice_input=True, voice_output=True),
        "vision": ProviderCapabilities(
            voice_input=True,
            voice_output=True,
            image_input=True,
            interruption=True,
        ),
        "avatar": ProviderCapabilities(
            voice_input=True,
            voice_output=True,
            image_input=True,
            interruption=True,
            avatar_video_output=True,
            synchronized_avatar_audio=True,
        ),
    }
    assert eligible_providers(providers, LiveMode.VOICE) == [
        "avatar", "vision", "voice"
    ]
    assert eligible_providers(providers, LiveMode.VOICE_VISION) == [
        "avatar", "vision"
    ]
    assert eligible_providers(providers, LiveMode.VOICE_VISION_AVATAR) == [
        "avatar"
    ]


def test_continuous_video_is_not_inferred_from_image_input():
    capabilities = ProviderCapabilities(
        voice_input=True,
        voice_output=True,
        image_input=True,
        interruption=True,
    )
    assert capabilities.image_input
    assert not capabilities.continuous_video_input
