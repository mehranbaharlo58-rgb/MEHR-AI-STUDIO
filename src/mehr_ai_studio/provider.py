"""Optional OpenAI-compatible chat-completions adapter."""
import httpx
from .config import settings

class ProviderNotConfigured(RuntimeError):
    pass

class ProviderError(RuntimeError):
    pass

def generate_text(prompt: str, system: str = "You are MEHR AI STUDIO, a precise content production assistant.") -> dict:
    if not settings.provider_base_url or not settings.provider_api_key or not settings.provider_model:
        raise ProviderNotConfigured("Configure AI_BASE_URL, AI_API_KEY, and AI_MODEL to enable generation.")
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
    try:
        with httpx.Client(timeout=settings.request_timeout) as client:
            response = client.post(
                url, json=payload,
                headers={"Authorization": f"Bearer {settings.provider_api_key}"},
            )
            response.raise_for_status()
            data = response.json()
        content = data["choices"][0]["message"]["content"]
        if not isinstance(content, str) or not content.strip():
            raise ValueError("Provider returned empty content")
        return {"text": content, "model": data.get("model", settings.provider_model)}
    except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
        raise ProviderError(f"AI provider request failed: {type(exc).__name__}") from exc
