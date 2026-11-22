"""End-to-end content workflow orchestration."""
from typing import Any

from .core import assess_text, build_content_brief
from .provider import ProviderError, ProviderNotConfigured, generate_text
from .store import DEFAULT_TENANT_ID, StudioStore


def run_content_workflow(
    store: StudioStore,
    goal: str,
    audience: str,
    channel: str,
    language: str = "Persian",
    tone: str = "clear and professional",
    context_key: str = "brand",
    tenant_id: str = DEFAULT_TENANT_ID,
) -> dict[str, Any]:
    """Build a brief, load optional tenant-scoped context, generate, and assess.

    The tenant ID must be supplied by trusted server-side authentication code.
    This function does not authenticate callers or establish an access boundary.
    """
    brief = build_content_brief(goal, audience, channel, language, tone)
    memory = (
        store.read_memory(context_key, tenant_id=tenant_id)
        if context_key.strip()
        else None
    )
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

    generated_text = generated["text"]
    return {
        "ok": True,
        "brief": brief,
        "context_loaded": memory is not None,
        "generated": generated,
        "assessment": assess_text(generated_text),
        "assessment_scope": "Structural checks only; factual accuracy is not verified.",
    }
