"""End-to-end content workflow orchestration through typed stages."""
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ValidationError

from .config import settings
from .contracts import (
    ContentBriefContract,
    GeneratedAssetContract,
    ProviderResultContract,
    QualityReportContract,
)
from .core import assess_text, build_content_brief
from .provider import ProviderError, ProviderNotConfigured, generate_text
from .store import DEFAULT_TENANT_ID, StudioStore
from .workflow_engine import StageDefinition, StageRegistry

CONTENT_PROMPT_VERSION = "content-v1"


class BriefStageInput(BaseModel):
    goal: str
    audience: str
    channel: str
    language: str = "Persian"
    tone: str = "clear and professional"


class ContextStageInput(BaseModel):
    context_key: str


class ContextStageOutput(BaseModel):
    context_key: str
    context_loaded: bool
    value: Any | None = None


class PromptStageInput(BaseModel):
    brief: ContentBriefContract
    context: ContextStageOutput


class PromptStageOutput(BaseModel):
    prompt: str


class GenerationStageInput(BaseModel):
    prompt: str


class AssetValidationStageInput(BaseModel):
    provider_result: ProviderResultContract


class AssessmentStageInput(BaseModel):
    content: str


def _build_content_registry(store: StudioStore, tenant_id: str) -> StageRegistry:
    """Build the typed stage pipeline for one tenant-scoped execution."""
    registry = StageRegistry()
    registry.register(
        StageDefinition(
            "brief",
            BriefStageInput,
            ContentBriefContract,
            lambda data: build_content_brief(
                data.goal, data.audience, data.channel, data.language, data.tone
            ),
        )
    )

    def load_context(data: ContextStageInput) -> ContextStageOutput:
        memory = (
            store.read_memory(data.context_key, tenant_id=tenant_id)
            if data.context_key.strip()
            else None
        )
        return ContextStageOutput(
            context_key=data.context_key,
            context_loaded=memory is not None,
            value=memory["value"] if memory else None,
        )

    registry.register(
        StageDefinition(
            "context",
            ContextStageInput,
            ContextStageOutput,
            load_context,
        )
    )
    registry.register(
        StageDefinition(
            "prompt",
            PromptStageInput,
            PromptStageOutput,
            lambda data: {
                "prompt": (
                    "Create content using this structured brief.\\n"
                    f"BRIEF: {data.brief.model_dump()}\\n"
                    f"SAVED CONTEXT ({data.context.context_key}): "
                    f"{data.context.value if data.context.context_loaded else 'not provided'}"
                )
            },
        )
    )
    registry.register(
        StageDefinition(
            "generation",
            GenerationStageInput,
            ProviderResultContract,
            lambda data: generate_text(data.prompt),
        )
    )
    registry.register(
        StageDefinition(
            "asset_validation",
            AssetValidationStageInput,
            GeneratedAssetContract,
            lambda data: GeneratedAssetContract(
                content=data.provider_result.text,
                format="text",
                model=data.provider_result.model,
            ),
        )
    )
    registry.register(
        StageDefinition(
            "assessment",
            AssessmentStageInput,
            QualityReportContract,
            lambda data: assess_text(data.content),
        )
    )
    return registry


def _execute_stage(
    registry: StageRegistry,
    store: StudioStore,
    stage_name: str,
    payload: BaseModel | dict[str, Any],
    *,
    run_id: str,
    attempt: int,
    tenant_id: str,
) -> BaseModel:
    """Execute, validate, then append the stage's immutable output."""
    output = registry.get(stage_name).execute(payload)
    store.save_stage_output(
        run_id=run_id,
        attempt=attempt,
        stage_name=stage_name,
        output=output.model_dump(mode="json"),
        tenant_id=tenant_id,
    )
    return output


def _workflow_output(
    generated: GeneratedAssetContract, assessment: QualityReportContract
) -> dict[str, Any]:
    return {
        "generated": {
            "text": generated.content,
            "model": generated.model,
            "format": generated.format,
        },
        "assessment": assessment.model_dump(),
        "assessment_scope": "Structural checks only; factual accuracy is not verified.",
    }


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
    attempt = 1
    registry = _build_content_registry(store, tenant_id)

    def persist(
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
                "model": model or settings.provider_model or None,
                "prompt_version": CONTENT_PROMPT_VERSION,
                "error_code": error_code,
                "result": result,
            },
            tenant_id=tenant_id,
        )

    brief = _execute_stage(
        registry, store, "brief",
        BriefStageInput(
            goal=goal, audience=audience, channel=channel,
            language=language, tone=tone,
        ),
        run_id=run_id, attempt=attempt, tenant_id=tenant_id,
    )
    assert isinstance(brief, ContentBriefContract)
    brief_data = brief.model_dump()
    persist("running", "brief", result={"brief": brief_data, "context_key": context_key})

    context = _execute_stage(
        registry, store, "context", ContextStageInput(context_key=context_key),
        run_id=run_id, attempt=attempt, tenant_id=tenant_id,
    )
    assert isinstance(context, ContextStageOutput)
    run_context = {
        "brief": brief_data,
        "context_key": context_key,
        "context_loaded": context.context_loaded,
    }
    prompt = _execute_stage(
        registry, store, "prompt",
        PromptStageInput(brief=brief, context=context),
        run_id=run_id, attempt=attempt, tenant_id=tenant_id,
    )
    assert isinstance(prompt, PromptStageOutput)
    persist("running", "generation", result=run_context)

    try:
        provider_result = _execute_stage(
            registry, store, "generation",
            GenerationStageInput(prompt=prompt.prompt),
            run_id=run_id, attempt=attempt, tenant_id=tenant_id,
        )
    except ProviderNotConfigured:
        persist("failed", "generation", error_code="provider_not_configured", result=run_context)
        return {
            "ok": False, "run_id": run_id, "stage": "generation",
            "error": "provider_not_configured",
            "message": "Configure the AI provider to enable generation.",
            "brief": brief_data, "context_loaded": context.context_loaded,
        }
    except ProviderError:
        persist("failed", "generation", error_code="provider_error", result=run_context)
        return {
            "ok": False, "run_id": run_id, "stage": "generation",
            "error": "provider_error", "message": "The AI provider request failed.",
            "brief": brief_data, "context_loaded": context.context_loaded,
        }
    except ValidationError:
        persist("failed", "validation", error_code="invalid_provider_response", result=run_context)
        return {
            "ok": False, "run_id": run_id, "stage": "validation",
            "error": "invalid_provider_response",
            "message": "The AI provider returned data that failed schema validation.",
            "brief": brief_data, "context_loaded": context.context_loaded,
        }

    try:
        assert isinstance(provider_result, ProviderResultContract)
        generated = _execute_stage(
            registry, store, "asset_validation",
            AssetValidationStageInput(provider_result=provider_result),
            run_id=run_id, attempt=attempt, tenant_id=tenant_id,
        )
        assert isinstance(generated, GeneratedAssetContract)
        assessment = _execute_stage(
            registry, store, "assessment",
            AssessmentStageInput(content=generated.content),
            run_id=run_id, attempt=attempt, tenant_id=tenant_id,
        )
        assert isinstance(assessment, QualityReportContract)
    except ValidationError:
        persist("failed", "validation", error_code="invalid_provider_response", result=run_context)
        return {
            "ok": False, "run_id": run_id, "stage": "validation",
            "error": "invalid_provider_response",
            "message": "The AI provider returned data that failed schema validation.",
            "brief": brief_data, "context_loaded": context.context_loaded,
        }

    output = _workflow_output(generated, assessment)
    persist(
        "succeeded", "completed", model=generated.model,
        result={**run_context, **output},
    )
    return {
        "ok": True, "run_id": run_id, "brief": brief_data,
        "context_loaded": context.context_loaded, **output,
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
            "ok": False, "error": "run_not_resumable",
            "run_id": run_id, "status": saved["status"],
        }

    checkpoint = saved.get("result") or {}
    brief_data = ContentBriefContract.model_validate(
        checkpoint.get("brief", {})
    ).model_dump()
    context_key = checkpoint.get("context_key", "brand")
    attempt = saved["attempt"] + 1
    created_at = saved["created_at"]
    registry = _build_content_registry(store, tenant_id)

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
                "run_id": run_id, "status": status, "current_stage": stage,
                "attempt": attempt, "created_at": created_at,
                "updated_at": datetime.now(UTC).isoformat(),
                "model": model or settings.provider_model or None,
                "prompt_version": CONTENT_PROMPT_VERSION,
                "error_code": error_code, "result": result,
            },
            tenant_id=tenant_id,
        )

    brief = _execute_stage(
        registry, store, "brief", BriefStageInput(**brief_data),
        run_id=run_id, attempt=attempt, tenant_id=tenant_id,
    )
    assert isinstance(brief, ContentBriefContract)
    context = _execute_stage(
        registry, store, "context", ContextStageInput(context_key=context_key),
        run_id=run_id, attempt=attempt, tenant_id=tenant_id,
    )
    assert isinstance(context, ContextStageOutput)
    run_context = {
        "brief": brief_data, "context_key": context_key,
        "context_loaded": context.context_loaded,
    }
    prompt = _execute_stage(
        registry, store, "prompt", PromptStageInput(brief=brief, context=context),
        run_id=run_id, attempt=attempt, tenant_id=tenant_id,
    )
    assert isinstance(prompt, PromptStageOutput)
    persist_resume("running", "generation", result=run_context)

    try:
        provider_result = _execute_stage(
            registry, store, "generation",
            GenerationStageInput(prompt=prompt.prompt),
            run_id=run_id, attempt=attempt, tenant_id=tenant_id,
        )
        assert isinstance(provider_result, ProviderResultContract)
        generated = _execute_stage(
            registry, store, "asset_validation",
            AssetValidationStageInput(provider_result=provider_result),
            run_id=run_id, attempt=attempt, tenant_id=tenant_id,
        )
        assert isinstance(generated, GeneratedAssetContract)
        assessment = _execute_stage(
            registry, store, "assessment",
            AssessmentStageInput(content=generated.content),
            run_id=run_id, attempt=attempt, tenant_id=tenant_id,
        )
        assert isinstance(assessment, QualityReportContract)
    except ProviderNotConfigured:
        persist_resume("failed", "generation", error_code="provider_not_configured", result=run_context)
        return {"ok": False, "run_id": run_id, "error": "provider_not_configured", "attempt": attempt}
    except ProviderError:
        persist_resume("failed", "generation", error_code="provider_error", result=run_context)
        return {"ok": False, "run_id": run_id, "error": "provider_error", "attempt": attempt}
    except ValidationError:
        persist_resume("failed", "validation", error_code="invalid_provider_response", result=run_context)
        return {"ok": False, "run_id": run_id, "error": "invalid_provider_response", "attempt": attempt}

    output = _workflow_output(generated, assessment)
    persist_resume(
        "succeeded", "completed", model=generated.model,
        result={**run_context, **output},
    )
    return {"ok": True, "run_id": run_id, "attempt": attempt, **output}
