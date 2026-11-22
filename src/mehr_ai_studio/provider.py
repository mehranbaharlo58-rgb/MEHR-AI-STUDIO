"""Optional OpenAI-compatible chat-completions adapter with bounded retries."""
import time

import httpx

from .config import settings


class ProviderNotConfigured(RuntimeError):
    """Raised when no complete provider configuration is available."""


class ProviderError(RuntimeError):
    """Raised when the provider request or response is invalid."""


_RETRYABLE_STATUS_CODES = {408, 409, 425, 429, 500, 502, 503, 504}


def _request_once(url: str, payload: dict, headers: dict) -> dict:
    with httpx.Client(timeout=settings.request_timeout) as client:
        response = client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()

    if not isinstance(data, dict):
        raise TypeError("Provider response must be a JSON object")
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise TypeError("Provider response has no valid choices")
    message = choices[0].get("message")
    if not isinstance(message, dict):
        raise TypeError("Provider response has no valid message")
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise ValueError("Provider returned empty content")
    return {"text": content, "model": data.get("model", settings.provider_model)}


def generate_text(
    prompt: str,
    system: str = "You are MEHR AI STUDIO, a precise content production assistant.",
) -> dict:
    if not settings.provider_base_url or not settings.provider_api_key or not settings.provider_model:
        raise ProviderNotConfigured(
            "Configure AI_BASE_URL, AI_API_KEY, and AI_MODEL to enable generation."
        )
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("prompt must be a non-empty string")
    if not isinstance(system, str) or not system.strip():
        raise ValueError("system must be a non-empty string")

    url = settings.provider_base_url.rstrip("/")
    if not url.endswith("/chat/completions"):
        url += "/chat/completions"
    payload = {
        "model": settings.provider_model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.6,
    }
    headers = {"Authorization": f"Bearer {settings.provider_api_key}"}
    max_attempts = settings.provider_max_attempts
    for attempt in range(1, max_attempts + 1):
        try:
            return _request_once(url, payload, headers)
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            retryable = status in _RETRYABLE_STATUS_CODES
            error_name = f"http_{status}"
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            retryable = True
            error_name = type(exc).__name__
        except (httpx.HTTPError, KeyError, IndexError, TypeError, AttributeError, ValueError) as exc:
            raise ProviderError(
                f"AI provider request failed: {type(exc).__name__}"
            ) from exc

        if not retryable or attempt >= max_attempts:
            raise ProviderError(f"AI provider request failed: {error_name}") from exc
        delay = settings.provider_retry_backoff * (2 ** (attempt - 1))
        if delay:
            time.sleep(delay)

    raise ProviderError("AI provider request failed: retry_limit_exhausted")
