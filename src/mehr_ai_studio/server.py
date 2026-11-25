"""MCP server entry point and tool registry."""
from mcp.server.fastmcp import FastMCP

from . import __version__
from .ai_registry_store import AIRegistryStore
from .ai_stack import AIModel, MatchRequest
from .config import settings
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


def main() -> None:
    app.run(transport="stdio")


if __name__ == "__main__":
    main()
