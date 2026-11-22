"""End-to-end content workflow orchestration."""
from typing import Any

from .contracts import (
    ContentBriefContract,
    GeneratedAssetContract,
    ProviderResultContract,
    QualityReportContract,
)
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
    """Build, validate, generate, and assess content for one trusted tenant.

    The tenant ID must be supplied by trusted server-side authentication code.
    This function does not authenticate callers or establish an access boundary.
    """
    brief = ContentBriefContract.model_validate(
        build_content_brief(goal, audience, channel, language, tone)
    ).model_dump()
    memory = (
        store.read_memory(context_key, tenant_id=tenant_id)
        if context_key.strip()
        else None
    )
    context = memory["value"] if memory else None
    prompt = (
        "Create content using this structured brief.\\n"
        f"BRIEF: {brief}\\n"
        f"SAVED CONTEXT ({context_key}): {context if context is not None else 'not provided'}"
    )
    try:
        raw_generated = generate_text(prompt)
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

    provider_result = ProviderResultContract.model_validate(raw_generated)
    generated = GeneratedAssetContract(
        content=provider_result.text,
        format="text",
        model=provider_result.model,
    )
    assessment = QualityReportContract.model_validate(
        assess_text(generated.content)
    )
    return {
        "ok": True,
        "brief": brief,
        "context_loaded": memory is not None,
        "generated": {
            "text": generated.content,
            "model": generated.model,
            "format": generated.format,
        },
        "assessment": assessment.model_dump(),
        "assessment_scope": "Structural checks only; factual accuracy is not verified.",
    }
