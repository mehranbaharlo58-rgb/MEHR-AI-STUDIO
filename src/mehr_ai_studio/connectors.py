"""Config-driven OpenAI-compatible connectors for hosted and local runtimes."""
from __future__ import annotations

import os
import re
from collections.abc import Mapping, Sequence
from urllib.parse import urlsplit

import httpx

from .ai_stack import AIModel
from .config import settings


class ConnectorConfigurationError(ValueError):
    """Raised when a connector is missing safe, usable configuration."""


def _chat_completions_url(endpoint: str) -> str:
    value = endpoint.strip().rstrip("/")
    parts = urlsplit(value)
    if not parts.hostname or parts.username or parts.password or parts.query or parts.fragment:
        raise ConnectorConfigurationError("invalid_provider_endpoint")
    local_hosts = {"localhost", "127.0.0.1", "::1"}
    if parts.scheme != "https" and not (parts.scheme == "http" and parts.hostname in local_hosts):
        raise ConnectorConfigurationError("provider_endpoint_must_use_https_or_loopback_http")
    if parts.path.endswith("/chat/completions"):
        return value
    return value + "/chat/completions"


class OpenAICompatibleAdapter:
    """Minimal async chat-completions adapter; secrets are injected, never stored in models."""

    def __init__(
        self,
        endpoint: str,
        model_name: str,
        api_key: str = "",
        timeout_s: float = 45.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if not endpoint.strip() or not model_name.strip():
            raise ConnectorConfigurationError("endpoint_and_model_id_required")
        if timeout_s <= 0:
            raise ConnectorConfigurationError("timeout_must_be_positive")
        self.url = _chat_completions_url(endpoint)
        self.model_name = model_name.strip()
        self.api_key = api_key.strip()
        self.timeout_s = timeout_s
        self.transport = transport

    async def __call__(self, model: AIModel, task: str) -> dict:
        if not task.strip():
            raise ValueError("task_must_be_non_empty")
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": "You are a precise, safe, task-focused AI assistant."},
                {"role": "user", "content": task},
            ],
            "temperature": 0.2,
            "stream": False,
        }
        async with httpx.AsyncClient(
            timeout=self.timeout_s, transport=self.transport
        ) as client:
            response = await client.post(self.url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
        if not isinstance(data, dict):
            raise ValueError("provider_response_must_be_object")
        choices = data.get("choices")
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
            raise ValueError("provider_response_missing_choices")
        message = choices[0].get("message")
        if not isinstance(message, dict):
            raise ValueError("provider_response_missing_message")
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise ValueError("provider_response_empty_content")
        return {
            "text": content,
            "model": data.get("model") or self.model_name,
            "provider": model.provider,
        }


def _provider_key_name(provider: str) -> str:
    slug = re.sub(r"[^A-Z0-9]+", "_", provider.upper()).strip("_")
    return f"MEHR_AI_API_KEY_{slug}"


def build_adapters(
    models: Sequence[AIModel],
    *,
    environ: Mapping[str, str] | None = None,
    default_endpoint: str | None = None,
    default_api_key: str | None = None,
    timeout_s: float | None = None,
) -> dict[str, OpenAICompatibleAdapter]:
    """Build only configured API/local adapters; never infer connectivity from catalogue data."""
    env = os.environ if environ is None else environ
    fallback_endpoint = settings.provider_base_url if default_endpoint is None else default_endpoint
    fallback_key = settings.provider_api_key if default_api_key is None else default_api_key
    request_timeout = settings.request_timeout if timeout_s is None else timeout_s
    adapters: dict[str, OpenAICompatibleAdapter] = {}
    for model in models:
        if model.access_mode not in {"openai_compatible", "local_runtime"}:
            continue
        endpoint = model.endpoint or fallback_endpoint
        model_name = model.model_id
        if not endpoint or not model_name:
            continue
        api_key = env.get(_provider_key_name(model.provider), "")
        if not api_key and endpoint.rstrip("/") == fallback_endpoint.rstrip("/"):
            api_key = fallback_key or ""
        if model.auth_required and not api_key:
            continue
        adapters[model.id] = OpenAICompatibleAdapter(
            endpoint=endpoint,
            model_name=model_name,
            api_key=api_key,
            timeout_s=request_timeout,
        )
    return adapters
