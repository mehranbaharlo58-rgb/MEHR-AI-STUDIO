"""Opt-in authenticated MCP server factory for multi-tenant deployments.

This module deliberately has no default identity provider. Callers must inject
an SDK TokenVerifier and AuthSettings from a configured authorization server.
The local stdio server remains separate and unchanged.
"""

from mcp.server.auth.provider import TokenVerifier
from mcp.server.auth.settings import AuthSettings
from mcp.server.fastmcp import FastMCP

from . import __version__
from .auth_context import current_request_tenant_id
from .config import settings
from .core import assess_text, build_content_brief
from .oidc import OIDCJWTTokenVerifier
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
            "version": __version__,
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



def build_oidc_authenticated_server_from_env(
    *, store: StudioStore | None = None
) -> FastMCP:
    """Build an authenticated server from explicit OIDC environment settings.

    Required variables: MEHR_OIDC_ISSUER_URL, MEHR_OIDC_JWKS_URL,
    MEHR_OIDC_AUDIENCE, and MEHR_MCP_RESOURCE_URL. This function never starts
    a listener; deployment code must choose and secure its HTTP hosting layer.
    """
    import os

    issuer_url = os.getenv("MEHR_OIDC_ISSUER_URL", "").strip()
    jwks_url = os.getenv("MEHR_OIDC_JWKS_URL", "").strip()
    audience = os.getenv("MEHR_OIDC_AUDIENCE", "").strip()
    resource_url = os.getenv("MEHR_MCP_RESOURCE_URL", "").strip()
    required_scopes = os.getenv(
        "MEHR_OIDC_REQUIRED_SCOPES", "studio:access"
    ).split()
    tenant_claim = os.getenv("MEHR_OIDC_TENANT_CLAIM", "tenant_id").strip()

    missing = [
        name
        for name, value in (
            ("MEHR_OIDC_ISSUER_URL", issuer_url),
            ("MEHR_OIDC_JWKS_URL", jwks_url),
            ("MEHR_OIDC_AUDIENCE", audience),
            ("MEHR_MCP_RESOURCE_URL", resource_url),
        )
        if not value
    ]
    if missing:
        raise ValueError("Missing OIDC configuration: " + ", ".join(missing))

    verifier = OIDCJWTTokenVerifier(
        issuer_url=issuer_url,
        jwks_url=jwks_url,
        audience=audience,
        resource_server_url=resource_url,
        required_scopes=required_scopes,
        tenant_claim=tenant_claim,
    )
    auth_settings = AuthSettings(
        issuer_url=issuer_url,
        resource_server_url=resource_url,
        required_scopes=required_scopes,
        validate_token_resource=True,
    )
    return build_authenticated_server(
        token_verifier=verifier,
        auth_settings=auth_settings,
        store=store,
    )
