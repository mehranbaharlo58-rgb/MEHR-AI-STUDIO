"""Opt-in authenticated MCP server factory for multi-tenant deployments.

This module deliberately has no default identity provider. Callers must inject
an SDK TokenVerifier and AuthSettings from a configured authorization server.
The local stdio server remains separate and unchanged.
"""

from typing import Any

from mcp.server.auth.provider import TokenVerifier
from mcp.server.auth.settings import AuthSettings
from mcp.server.fastmcp import FastMCP

from .auth_context import current_request_tenant_id
from .config import settings
from .core import assess_text, build_content_brief
from .provider import ProviderError, ProviderNotConfigured, generate_text
from .store import StudioStore
from .workflow import run_content_workflow as execute_content_workflow


def _validate_auth_configuration(
    token_verifier: TokenVerifier, auth_settings: AuthSettings
) -> None:
    """Reject incomplete resource-server configuration before creating HTTP app."""
    if token_verifier is None or not callable(getattr(token_verifier, "verify_token", None)):
        raise ValueError("A real SDK-compatible TokenVerifier is required")
    issuer_url = str(getattr(auth_settings, "issuer_url", "") or "")
    resource_url = str(getattr(auth_settings, "resource_server_url", "") or "")
    required_scopes = getattr(auth_settings, "required_scopes", None)
    if not issuer_url.startswith("https://"):
        raise ValueError("OAuth issuer_url must use HTTPS")
    if not resource_url.startswith("https://"):
        raise ValueError("OAuth resource_server_url must use HTTPS")
    if not required_scopes:
        raise ValueError("At least one required OAuth scope must be configured")


def build_authenticated_server(
    *,
    token_verifier: TokenVerifier,
    auth_settings: AuthSettings,
    store: StudioStore | None = None,
) -> FastMCP:
    """Build, but do not start, a Streamable HTTP server with injected OAuth.

    The injected verifier must validate signature/introspection, issuer,
    audience/resource, expiry, and scopes, and return only trusted claims.
    Tenant IDs are resolved from that verified request context, never tool args.
    """
    _validate_auth_configuration(token_verifier, auth_settings)
    tenant_store = store or StudioStore(settings.database_path)
    mcp = FastMCP(
        "MEHR AI STUDIO",
        token_verifier=token_verifier,
        auth=auth_settings,
    )

    @mcp.tool()
    def studio_status() -> dict:
        """Return application identity and configured provider status."""
        configured = bool(
            settings.provider_base_url
            and settings.provider_api_key
            and settings.provider_model
        )
        return {
            "name": "MEHR AI STUDIO",
            "version": "0.4.1",
            "status": "development",
            "memory": "sqlite",
            "ai_provider_configured": configured,
        }

    @mcp.tool()
    def create_content_brief(
        goal: str,
        audience: str,
        channel: str,
        language: str = "Persian",
        tone: str = "clear and professional",
    ) -> dict:
        """Create a structured content brief."""
        return build_content_brief(goal, audience, channel, language, tone)

    @mcp.tool()
    def assess_content(text: str) -> dict:
        """Run structural checks; this does not fact-check content."""
        return assess_text(text)

    @mcp.tool()
    def save_project_memory(key: str, value: str) -> dict:
        """Save memory in the authenticated caller's tenant."""
        return tenant_store.save_memory(
            key, value, tenant_id=current_request_tenant_id()
        )

    @mcp.tool()
    def read_project_memory(key: str) -> dict:
        """Read memory only from the authenticated caller's tenant."""
        tenant_id = current_request_tenant_id()
        result = tenant_store.read_memory(key, tenant_id=tenant_id)
        return result or {"found": False, "key": key}

    @mcp.tool()
    def record_content_feedback(item_type: str, rating: int, note: str = "") -> dict:
        """Record feedback in the authenticated caller's tenant."""
        return tenant_store.record_feedback(
            item_type, rating, note, tenant_id=current_request_tenant_id()
        )

    @mcp.tool()
    def get_feedback_insights() -> dict:
        """Return feedback analytics for the authenticated caller's tenant."""
        return tenant_store.feedback_insights(
            tenant_id=current_request_tenant_id()
        )

    @mcp.tool()
    def generate_with_ai(
        prompt: str,
        system: str = "You are MEHR AI STUDIO, a precise content production assistant.",
    ) -> dict:
        """Generate text using the configured AI provider."""
        try:
            return {"ok": True, **generate_text(prompt, system)}
        except ProviderNotConfigured as exc:
            return {"ok": False, "error": "provider_not_configured", "message": str(exc)}
        except ProviderError as exc:
            return {"ok": False, "error": "provider_error", "message": str(exc)}

    @mcp.tool()
    def run_content_workflow(
        goal: str,
        audience: str,
        channel: str,
        language: str = "Persian",
        tone: str = "clear and professional",
        context_key: str = "brand",
    ) -> dict:
        """Run the content workflow inside the authenticated caller's tenant."""
        return execute_content_workflow(
            tenant_store,
            goal,
            audience,
            channel,
            language,
            tone,
            context_key,
            tenant_id=current_request_tenant_id(),
        )

    return mcp
