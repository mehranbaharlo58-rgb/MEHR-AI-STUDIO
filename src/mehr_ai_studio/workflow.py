"""End-to-end content workflow orchestration."""
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pydantic import ValidationError

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
    """Build, validate, generate, assess, and persist one tenant-scoped run.

    The tenant ID must be supplied by trusted server-side authentication code.
    This function does not authenticate callers or establish an access boundary.
    """
    run_id = uuid4().hex
    created_at = datetime.now(UTC).isoformat()

    def persist(
        status: str,
        stage: str,
        *,
        error_code: str | None = None,
        model: str | None = None,
        result: dict[str, Any] | None = None,
        attempt: int = 1,
    ) -> None:
        store.save_workflow_run(
            {
                "run_id": run_id,
                "status": status,
                "current_stage": stage,
                "attempt": attempt,
                "created_at": created_at,
                "updated_at": datetime.now(UTC).isoformat(),
                "model": model,
                "error_code": error_code,
                "result": result,
            },
            tenant_id=tenant_id,
        )

    brief = ContentBriefContract.model_validate(
        build_content_brief(goal, audience, channel, language, tone)
    ).model_dump()
    persist(
        "running",
        "brief",
        result={"brief": brief, "context_key": context_key},
    )
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
    run_context = {
        "brief": brief,
        "context_key": context_key,
        "context_loaded": memory is not None,
    }
    persist("running", "generation", result=run_context)
    try:
        raw_generated = generate_text(prompt)
    except ProviderNotConfigured:
        persist(
            "failed",
            "generation",
            error_code="provider_not_configured",
            result=run_context,
        )
        return {
            "ok": False,
            "run_id": run_id,
            "stage": "generation",
            "error": "provider_not_configured",
            "message": "Configure the AI provider to enable generation.",
            "brief": brief,
            "context_loaded": memory is not None,
        }
    except ProviderError:
        persist(
            "failed",
            "generation",
            error_code="provider_error",
            result=run_context,
        )
        return {
            "ok": False,
            "run_id": run_id,
            "stage": "generation",
            "error": "provider_error",
            "message": "The AI provider request failed.",
            "brief": brief,
            "context_loaded": memory is not None,
        }

    try:
        provider_result = ProviderResultContract.model_validate(raw_generated)
        generated = GeneratedAssetContract(
            content=provider_result.text,
            format="text",
            model=provider_result.model,
        )
        assessment = QualityReportContract.model_validate(
            assess_text(generated.content)
        )
    except ValidationError:
        persist(
            "failed",
            "validation",
            error_code="invalid_provider_response",
            result=run_context,
        )
        return {
            "ok": False,
            "run_id": run_id,
            "stage": "validation",
            "error": "invalid_provider_response",
            "message": "The AI provider returned data that failed schema validation.",
            "brief": brief,
            "context_loaded": memory is not None,
        }

    output = {
        "generated": {
            "text": generated.content,
            "model": generated.model,
            "format": generated.format,
        },
        "assessment": assessment.model_dump(),
        "assessment_scope": "Structural checks only; factual accuracy is not verified.",
    }
    persist(
        "succeeded",
        "completed",
        model=generated.model,
        result={**run_context, **output},
    )
    return {
        "ok": True,
        "run_id": run_id,
        "brief": brief,
        "context_loaded": memory is not None,
        **output,
    }


def resume_content_workflow(
    store: StudioStore,
    run_id: str,
    tenant_id: str = DEFAULT_TENANT_ID,
) -> dict[str, Any]:
    """Resume a failed generation from its persisted, tenant-scoped brief."""
    saved = store.read_workflow_run(run_id, tenant_id=tenant_id)
    if saved is None:
        return {"ok": False, "error": "run_not_found", "run_id": run_id}
    if saved["status"] != "failed":
        return {
            "ok": False,
            "error": "run_not_resumable",
            "run_id": run_id,
            "status": saved["status"],
        }

    checkpoint = saved.get("result") or {}
    brief = ContentBriefContract.model_validate(checkpoint.get("brief", {})).model_dump()
    context_key = checkpoint.get("context_key", "brand")
    memory = (
        store.read_memory(context_key, tenant_id=tenant_id)
        if isinstance(context_key, str) and context_key.strip()
        else None
    )
    context = memory["value"] if memory else None
    prompt = (
        "Create content using this structured brief.\\n"
        f"BRIEF: {brief}\\n"
        f"SAVED CONTEXT ({context_key}): {context if context is not None else 'not provided'}"
    )
    attempt = saved["attempt"] + 1
    created_at = saved["created_at"]

    def persist_resume(
        status: str,
        stage: str,
        *,
        error_code: str | None = None,
        model: str | None = None,
        result: dict[str, Any] | None = None,
    ) -> None:
        store.save_workflow_run(
            {
                "run_id": run_id,
                "status": status,
                "current_stage": stage,
                "attempt": attempt,
                "created_at": created_at,
                "updated_at": datetime.now(UTC).isoformat(),
                "model": model,
                "error_code": error_code,
                "result": result,
            },
            tenant_id=tenant_id,
        )

    run_context = {
        "brief": brief,
        "context_key": context_key,
        "context_loaded": memory is not None,
    }
    persist_resume("running", "generation", result=run_context)
    try:
        raw_generated = generate_text(prompt)
        provider_result = ProviderResultContract.model_validate(raw_generated)
        generated = GeneratedAssetContract(
            content=provider_result.text,
            format="text",
            model=provider_result.model,
        )
        assessment = QualityReportContract.model_validate(
            assess_text(generated.content)
        )
    except ProviderNotConfigured:
        persist_resume(
            "failed",
            "generation",
            error_code="provider_not_configured",
            result=run_context,
        )
        return {
            "ok": False,
            "run_id": run_id,
            "error": "provider_not_configured",
            "attempt": attempt,
        }
    except ProviderError:
        persist_resume(
            "failed",
            "generation",
            error_code="provider_error",
            result=run_context,
        )
        return {
            "ok": False,
            "run_id": run_id,
            "error": "provider_error",
            "attempt": attempt,
        }
    except ValidationError:
        persist_resume(
            "failed",
            "validation",
            error_code="invalid_provider_response",
            result=run_context,
        )
        return {
            "ok": False,
            "run_id": run_id,
            "error": "invalid_provider_response",
            "attempt": attempt,
        }

    output = {
        "generated": {
            "text": generated.content,
            "model": generated.model,
            "format": generated.format,
        },
        "assessment": assessment.model_dump(),
        "assessment_scope": "Structural checks only; factual accuracy is not verified.",
    }
    persist_resume(
        "succeeded",
        "completed",
        model=generated.model,
        result={**run_context, **output},
    )
    return {
        "ok": True,
        "run_id": run_id,
        "attempt": attempt,
        **output,
    }
