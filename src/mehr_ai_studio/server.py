"""MCP server entry point."""
from mcp.server.fastmcp import FastMCP
from . import __version__
from .core import assess_text, build_content_brief

app = FastMCP("MEHR AI STUDIO")

@app.tool()
def studio_status() -> dict:
    """Return application identity and current development version."""
    return {"name": "MEHR AI STUDIO", "version": __version__, "status": "development"}

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

def main() -> None:
    app.run(transport="stdio")

if __name__ == "__main__":
    main()
