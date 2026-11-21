from types import SimpleNamespace

import pytest

from mehr_ai_studio import provider


def test_provider_requires_configuration(monkeypatch):
    monkeypatch.setattr(
        provider,
        "settings",
        SimpleNamespace(
            provider_base_url="",
            provider_api_key="",
            provider_model="",
        ),
    )
    with pytest.raises(provider.ProviderNotConfigured):
        provider.generate_text("hello")
