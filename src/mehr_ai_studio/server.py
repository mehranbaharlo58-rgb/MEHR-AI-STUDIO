"""MCP server entry point and tool registry."""
from datetime import UTC, datetime

from mcp.server.fastmcp import FastMCP

from . import __version__
from .ai_registry_store import AIRegistryStore
from .ai_stack import AIExecutionManager, AIModel, AIRegistry, MatchRequest
from .catalog import seed_ai_catalog as seed_catalog_records
from .config import settings
from .connectors import build_adapters, smoke_test_adapter
from .core import assess_text, build_content_brief
from .provider import ProviderError, ProviderNotConfigured, generate_text
from .store import DEFAULT_TENANT_ID, StudioStore
from .workflow import resume_content_workflow as execute_resume_content_workflow
from .workflow import run_content_workflow as execute_content_workflow

app = FastMCP("MEHR AI STUDIO")
store = StudioStore(settings.database_path)
ai_registry = AIRegistryStore(settings.database_path)


@app.tool()
def studio_status() -> dict:
    """Return application identity, version, and configured provider status."""
    configured = bool(settings.provider_base_url and settings.provider_api_key and settings.provider_model)
    return {
        "name": "MEHR AI STUDIO",
        "version": __version__,
        "status": "development",
        "memory": "sqlite",
        "ai_provider_configured": configured,
    }


@app.tool()
def create_content_brief(goal: str, audience: str, channel: str,
                         language: str = "Persian",
                         tone: str = "clear and professional") -> dict:
    """Create a structured content brief from a goal, audience, and channel."""
    return build_content_brief(goal, audience, channel, language, tone)


@app.tool()
def assess_content(text: str) -> dict:
    """Run basic structural checks; this does not fact-check the content."""
    return assess_text(text)


@app.tool()
def save_project_memory(key: str, value: str) -> dict:
    """Save explicit project or brand context as a text value."""
    return store.save_memory(key, value)


@app.tool()
def read_project_memory(key: str) -> dict:
    """Read a previously saved project or brand context value."""
    result = store.read_memory(key)
    return result or {"found": False, "key": key}


@app.tool()
def record_content_feedback(item_type: str, rating: int, note: str = "") -> dict:
    """Record human feedback with a 1-to-5 rating."""
    return store.record_feedback(item_type, rating, note)


@app.tool()
def get_feedback_insights() -> dict:
    """Summarize stored ratings. This is analytics, not model training."""
    return store.feedback_insights()


@app.tool()
def read_workflow_run(run_id: str) -> dict:
    """Read a saved workflow run from the local single-user store."""
    result = store.read_workflow_run(run_id, tenant_id=DEFAULT_TENANT_ID)
    return result or {"found": False, "run_id": run_id}


@app.tool()
def list_workflow_runs(limit: int = 20) -> dict:
    """List recent workflow runs from the local single-user store."""
    return {"runs": store.list_workflow_runs(DEFAULT_TENANT_ID, limit=limit)}


@app.tool()
def resume_content_workflow(run_id: str) -> dict:
    """Resume a failed local workflow from its saved checkpoint."""
    return execute_resume_content_workflow(
        store, run_id, tenant_id=DEFAULT_TENANT_ID
    )


@app.tool()
def generate_with_ai(prompt: str, system: str = "You are MEHR AI STUDIO, a precise content production assistant.") -> dict:
    """Generate text using an optional configured OpenAI-compatible provider."""
    try:
        return {"ok": True, **generate_text(prompt, system)}
    except ProviderNotConfigured as exc:
        return {"ok": False, "error": "provider_not_configured", "message": str(exc)}
    except ProviderError as exc:
        return {"ok": False, "error": "provider_error", "message": str(exc)}


@app.tool()
def run_content_workflow(goal: str, audience: str, channel: str,
                         language: str = "Persian",
                         tone: str = "clear and professional",
                         context_key: str = "brand") -> dict:
    """Load saved context, build a brief, generate content, and assess structure."""
    return execute_content_workflow(store, goal, audience, channel, language, tone, context_key)



@app.tool()
def register_ai_model(model: dict) -> dict:
    """Register or update an AI model/tool record; registration does not connect it."""
    try:
        return ai_registry.upsert(AIModel.model_validate(model))
    except Exception as exc:  # noqa: BLE001 - return contract errors to the caller
        return {"saved": False, "error": "invalid_model", "detail": str(exc)[:500]}


@app.tool()
def list_ai_models(status: str | None = None, category: str | None = None) -> dict:
    """List registered AI entries and operational-state counts."""
    return {
        "models": [item.model_dump() for item in ai_registry.list(status=status, category=category)],
        "counts": ai_registry.counts(),
    }


@app.tool()
def match_ai_models(
    task: str,
    category: str | None = None,
    required_capabilities: list[str] | None = None,
    input_modality: str = "text",
    output_modality: str = "text",
    prefer_free: bool = True,
    operational_only: bool = True,
    limit: int = 10,
) -> dict:
    """Rank registered AI entries for a task with explicit operational-state gating."""
    request = MatchRequest(
        task=task, category=category,
        required_capabilities=required_capabilities or [],
        input_modality=input_modality, output_modality=output_modality,
        prefer_free=prefer_free, operational_only=operational_only, limit=limit,
    )
    return {"matches": ai_registry.match(request), "counts": ai_registry.counts()}



@app.tool()
def seed_ai_catalog() -> dict:
    """Seed the curated 100-entry AI catalogue without overwriting existing records."""
    return seed_catalog_records(ai_registry)



@app.tool()
async def execute_ai_task(
    task: str,
    category: str | None = None,
    limit: int = 3,
) -> dict:
    """Match and execute only configured models with usable connector credentials."""
    if not 1 <= limit <= 10:
        return {"ok": False, "error": "limit_must_be_between_1_and_10"}
    models = ai_registry.list()
    matches = ai_registry.match(MatchRequest(
        task=task,
        category=category,
        prefer_free=True,
        operational_only=True,
        limit=limit,
    ))
    adapters = build_adapters(
        models,
        default_endpoint=settings.provider_base_url,
        default_api_key=settings.provider_api_key,
    )
    selected_ids = [item["model_id"] for item in matches if item["model_id"] in adapters]
    skipped = [
        {"model_id": item["model_id"], "reason": "connector_or_credentials_not_configured"}
        for item in matches if item["model_id"] not in adapters
    ]
    if not selected_ids:
        return {
            "ok": False,
            "error": "no_runnable_models",
            "matches": matches,
            "skipped": skipped,
            "registry_counts": ai_registry.counts(),
        }
    registry = AIRegistry(model for model in models if model.id in selected_ids)
    manager = AIExecutionManager(
        registry,
        {model_id: adapters[model_id] for model_id in selected_ids},
        max_parallel=min(3, len(selected_ids)),
        timeout_s=settings.request_timeout,
    )
    execution = await manager.execute_with_fallback(selected_ids, task)
    return {
        "ok": execution["ok"],
        "selected_model_ids": selected_ids,
        "selected_model_id": execution["selected_model_id"],
        "attempted_model_ids": execution["attempted_model_ids"],
        "fallback_used": execution["fallback_used"],
        "skipped": skipped,
        "results": execution["results"],
        "registry_counts": ai_registry.counts(),
    }



@app.tool()
async def test_ai_connector(model_id: str) -> dict:
    """Explicitly smoke-test one configured connector and record verified health."""
    models = ai_registry.list()
    model = next((item for item in models if item.id == model_id), None)
    if model is None:
        return {"ok": False, "error": "model_not_registered"}
    if model.status not in {"configured", "tested", "degraded"}:
        return {"ok": False, "error": "model_not_operational", "status": model.status}
    adapters = build_adapters(
        models,
        default_endpoint=settings.provider_base_url,
        default_api_key=settings.provider_api_key,
    )
    adapter = adapters.get(model_id)
    if adapter is None:
        return {"ok": False, "error": "connector_or_credentials_not_configured"}
    try:
        probe = await smoke_test_adapter(
            adapter, model, timeout_s=min(settings.request_timeout, 20.0)
        )
    except TimeoutError:
        updated = model.model_copy(update={"status": "degraded"})
        ai_registry.upsert(updated)
        return {"ok": False, "error": "timeout", "status": "degraded"}
    except Exception as exc:  # noqa: BLE001 - never expose provider response bodies or secrets
        updated = model.model_copy(update={"status": "degraded"})
        ai_registry.upsert(updated)
        return {
            "ok": False,
            "error": type(exc).__name__,
            "status": "degraded",
        }
    verified_at = datetime.now(UTC).isoformat()
    updated = model.model_copy(update={
        "status": "tested",
        "verification_status": "integration_tested",
        "last_verified_at": verified_at,
        "latency_ms": max(1, round(probe["latency_ms"])),
    })
    ai_registry.upsert(updated)
    return {
        "ok": True,
        "model_id": model_id,
        "status": "tested",
        "verification_status": "integration_tested",
        "last_verified_at": verified_at,
        "latency_ms": probe["latency_ms"],
        "response": probe["response"],
    }


def main() -> None:
    app.run(transport="stdio")


if __name__ == "__main__":
    main()
