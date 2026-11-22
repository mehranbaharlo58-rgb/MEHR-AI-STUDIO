from types import SimpleNamespace

import httpx
import pytest

from mehr_ai_studio import provider


def configured_settings(**overrides):
    values = {
        "provider_base_url": "https://api.example.test/v1",
        "provider_api_key": "test-secret",
        "provider_model": "test-model",
        "request_timeout": 12,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_provider_requires_configuration(monkeypatch):
    monkeypatch.setattr(provider, "settings", configured_settings(provider_base_url=""))
    with pytest.raises(provider.ProviderNotConfigured):
        provider.generate_text("hello")


@pytest.mark.parametrize("prompt,system", [("", "system"), ("  ", "system"), ("hello", ""), ("hello", "  ")])
def test_provider_rejects_empty_inputs(monkeypatch, prompt, system):
    monkeypatch.setattr(provider, "settings", configured_settings())
    with pytest.raises(ValueError):
        provider.generate_text(prompt, system)


def test_provider_success_appends_chat_completions_and_parses_response(monkeypatch):
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "model": "resolved-model",
                "choices": [{"message": {"content": "Generated result"}}],
            }

    class FakeClient:
        def __init__(self, timeout):
            captured["timeout"] = timeout

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, url, json, headers):
            captured.update({"url": url, "json": json, "headers": headers})
            return FakeResponse()

    monkeypatch.setattr(provider, "settings", configured_settings())
    monkeypatch.setattr(provider.httpx, "Client", FakeClient)

    result = provider.generate_text("Write a short post", "Be precise")

    assert result == {"text": "Generated result", "model": "resolved-model"}
    assert captured["url"] == "https://api.example.test/v1/chat/completions"
    assert captured["timeout"] == 12
    assert captured["headers"]["Authorization"] == "Bearer test-secret"
    assert captured["json"]["messages"] == [
        {"role": "system", "content": "Be precise"},
        {"role": "user", "content": "Write a short post"},
    ]


def test_provider_does_not_duplicate_chat_completions(monkeypatch):
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"content": "ok"}}]}

    class FakeClient:
        def __init__(self, timeout):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, url, json, headers):
            captured["url"] = url
            return FakeResponse()

    monkeypatch.setattr(
        provider,
        "settings",
        configured_settings(provider_base_url="https://api.example.test/v1/chat/completions"),
    )
    monkeypatch.setattr(provider.httpx, "Client", FakeClient)

    provider.generate_text("hello")

    assert captured["url"] == "https://api.example.test/v1/chat/completions"


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {},
        {"choices": []},
        {"choices": ["invalid"]},
        {"choices": [{"message": None}]},
        {"choices": [{"message": {"content": ""}}]},
    ],
)
def test_provider_rejects_malformed_responses(monkeypatch, payload):
    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return payload

    class FakeClient:
        def __init__(self, timeout):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, url, json, headers):
            return FakeResponse()

    monkeypatch.setattr(provider, "settings", configured_settings())
    monkeypatch.setattr(provider.httpx, "Client", FakeClient)

    with pytest.raises(provider.ProviderError):
        provider.generate_text("hello")


def test_provider_wraps_http_errors_without_leaking_response_body(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            request = httpx.Request("POST", "https://api.example.test/v1/chat/completions")
            response = httpx.Response(401, request=request, text="sensitive provider response")
            raise httpx.HTTPStatusError("unauthorized", request=request, response=response)

    class FakeClient:
        def __init__(self, timeout):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, url, json, headers):
            return FakeResponse()

    monkeypatch.setattr(provider, "settings", configured_settings())
    monkeypatch.setattr(provider.httpx, "Client", FakeClient)

    with pytest.raises(provider.ProviderError) as error:
        provider.generate_text("hello")

    assert "sensitive provider response" not in str(error.value)


def test_provider_retries_transient_status_then_succeeds(monkeypatch):
    calls = {"count": 0}
    sleeps = []

    class FakeResponse:
        def __init__(self, status):
            self.status = status

        def raise_for_status(self):
            if self.status >= 400:
                request = httpx.Request("POST", "https://api.example.test/v1/chat/completions")
                response = httpx.Response(self.status, request=request)
                raise httpx.HTTPStatusError("temporary", request=request, response=response)

        def json(self):
            return {"choices": [{"message": {"content": "recovered"}}]}

    class FakeClient:
        def __init__(self, timeout):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, url, json, headers):
            calls["count"] += 1
            return FakeResponse(503 if calls["count"] == 1 else 200)

    monkeypatch.setattr(provider, "settings", configured_settings(
        provider_max_attempts=3, provider_retry_backoff=0.25
    ))
    monkeypatch.setattr(provider.httpx, "Client", FakeClient)
    monkeypatch.setattr(provider.time, "sleep", sleeps.append)

    result = provider.generate_text("hello")

    assert result["text"] == "recovered"
    assert calls["count"] == 2
    assert sleeps == [0.25]


def test_provider_does_not_retry_permanent_client_error(monkeypatch):
    calls = {"count": 0}

    class FakeResponse:
        def raise_for_status(self):
            request = httpx.Request("POST", "https://api.example.test/v1/chat/completions")
            response = httpx.Response(401, request=request)
            raise httpx.HTTPStatusError("unauthorized", request=request, response=response)

    class FakeClient:
        def __init__(self, timeout):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, url, json, headers):
            calls["count"] += 1
            return FakeResponse()

    monkeypatch.setattr(provider, "settings", configured_settings(
        provider_max_attempts=4, provider_retry_backoff=0
    ))
    monkeypatch.setattr(provider.httpx, "Client", FakeClient)

    with pytest.raises(provider.ProviderError):
        provider.generate_text("hello")

    assert calls["count"] == 1


def test_provider_stops_after_bounded_transient_failures(monkeypatch):
    calls = {"count": 0}

    class FakeResponse:
        def raise_for_status(self):
            request = httpx.Request("POST", "https://api.example.test/v1/chat/completions")
            response = httpx.Response(429, request=request)
            raise httpx.HTTPStatusError("rate limited", request=request, response=response)

    class FakeClient:
        def __init__(self, timeout):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, url, json, headers):
            calls["count"] += 1
            return FakeResponse()

    monkeypatch.setattr(provider, "settings", configured_settings(
        provider_max_attempts=2, provider_retry_backoff=0
    ))
    monkeypatch.setattr(provider.httpx, "Client", FakeClient)

    with pytest.raises(provider.ProviderError):
        provider.generate_text("hello")

    assert calls["count"] == 2
