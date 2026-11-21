"""End-to-end content workflow orchestration."""
from typing import Any

from .core import assess_text, build_content_brief
from .provider import ProviderError, ProviderNotConfigured, generate_text
from .store import StudioStore


def run_content_workflow(
    store: StudioStore,
    goal: str,
    audience: str,
    channel: str,
    language: str = "Persian",
    tone: str = "clear and professional",
    context_key: str = "brand",
) -> dict[str, Any]:
    """Build a brief, load optional saved context, generate, and assess output.

    The workflow never invents feedback ratings or claims factual verification.
    """
    brief = build_content_brief(goal, audience, channel, language, tone)
    memory = store.read_memory(context_key) if context_key.strip() else None
    context = memory["value"] if memory else None
    prompt = (
        "Create content using this structured brief.\n"
        f"BRIEF: {brief}\n"
        f"SAVED CONTEXT ({context_key}): {context if context is not None else 'not provided'}"
    )
    try:
        generated = generate_text(prompt)
    except ProviderNotConfigured as exc:
        return {
            "ok": False,
            "stage": "generation",
            "error": "provider_not_configured",
            "message": str(exc),
            "brief": brief,
            "context_loaded": memory is not None,
        }
    except ProviderError as exc:
        return {
            "ok": False,
            "stage": "generation",
            "error": "provider_error",
            "message": str(exc),
            "brief": brief,
            "context_loaded": memory is not None,
        }

    text = generated["text"]
    return {
        "ok": True,
        "brief": brief,
        "context_loaded": memory is not None,
        "generated": generated,
        "assessment": assess_text(text),
        "assessment_scope": "Structural checks only; factual accuracy is not verified.",
    }
