"""MCP server entry point and tool registry."""
from mcp.server.fastmcp import FastMCP

from . import __version__
from .config import settings
from .core import assess_text, build_content_brief
from .provider import ProviderError, ProviderNotConfigured, generate_text
from .store import StudioStore
from .workflow import run_content_workflow as execute_content_workflow

app = FastMCP("MEHR AI STUDIO")
store = StudioStore(settings.database_path)


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


def main() -> None:
    app.run(transport="stdio")


if __name__ == "__main__":
    main()
