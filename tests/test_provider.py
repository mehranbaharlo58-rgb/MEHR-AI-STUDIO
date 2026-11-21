import pytest
from mehr_ai_studio import provider

def test_provider_requires_configuration(monkeypatch):
    monkeypatch.setattr(provider.settings, "provider_base_url", "")
    monkeypatch.setattr(provider.settings, "provider_api_key", "")
    monkeypatch.setattr(provider.settings, "provider_model", "")
    with pytest.raises(provider.ProviderNotConfigured):
        provider.generate_text("hello")
