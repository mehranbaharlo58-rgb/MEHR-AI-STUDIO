"""Opt-in authenticated MCP server factory for multi-tenant deployments.

This module deliberately has no default identity provider. Callers must inject
an SDK TokenVerifier and AuthSettings from a configured authorization server.
The local stdio server remains separate and unchanged.
"""

from datetime import UTC, datetime
from urllib.parse import urlparse

from mcp.server.auth.provider import TokenVerifier
from mcp.server.auth.settings import AuthSettings
from mcp.server.fastmcp import FastMCP

from . import __version__
from .auth_context import current_request_tenant_id
from .config import settings
from .ai_registry_store import AIRegistryStore
from .ai_stack import AIExecutionManager, AIModel, AIRegistry, MatchRequest
from .catalog import seed_ai_catalog as seed_catalog_records
from .connectors import build_adapters, smoke_test_adapter
from .core import assess_text, build_content_brief
from .oidc import OIDCJWTTokenVerifier
from .provider import ProviderError, ProviderNotConfigured, generate_text
from .store import StudioStore
from .workflow import resume_content_workflow as execute_resume_content_workflow
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
    for name, value in (
        ("issuer_url", issuer_url),
        ("resource_server_url", resource_url),
    ):
        parsed = urlparse(value)
        if parsed.scheme != "https" or not parsed.netloc or parsed.username:
            raise ValueError(f"OAuth {name} must be an absolute HTTPS URL")
    if (
        not isinstance(required_scopes, (list, tuple))
        or not required_scopes
        or any(not isinstance(scope, str) or not scope.strip() for scope in required_scopes)
    ):
        raise ValueError("At least one non-empty required OAuth scope must be configured")


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
    def read_workflow_run(run_id: str) -> dict:
        """Read a saved run only from the authenticated caller's tenant."""
        tenant_id = current_request_tenant_id()
        result = tenant_store.read_workflow_run(run_id, tenant_id=tenant_id)
        return result or {"found": False, "run_id": run_id}

    @mcp.tool()
    def list_workflow_runs(limit: int = 20) -> dict:
        """List recent workflow runs for the authenticated caller's tenant."""
        return {
            "runs": tenant_store.list_workflow_runs(
                tenant_id=current_request_tenant_id(), limit=limit
            )
        }

    @mcp.tool()
    def resume_content_workflow(run_id: str) -> dict:
        """Resume a failed workflow inside the authenticated caller's tenant."""
        return execute_resume_content_workflow(
            tenant_store,
            run_id,
            tenant_id=current_request_tenant_id(),
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


    def tenant_ai_registry() -> AIRegistryStore:
        """Resolve the registry from the verified caller tenant, never tool input."""
        return AIRegistryStore(
            settings.database_path,
            tenant_id=current_request_tenant_id(),
        )

    @mcp.tool()
    def register_ai_model(model: dict) -> dict:
        """Register an AI model in the authenticated tenant; this does not connect it."""
        try:
            return tenant_ai_registry().upsert(AIModel.model_validate(model))
        except Exception:  # noqa: BLE001 - do not echo submitted values or secrets
            return {"saved": False, "error": "invalid_model"}

    @mcp.tool()
    def list_ai_models(status: str | None = None, category: str | None = None) -> dict:
        """List only the authenticated tenant's AI catalogue and status counts."""
        registry = tenant_ai_registry()
        return {
            "models": [
                item.model_dump() for item in registry.list(
                    status=status, category=category
                )
            ],
            "counts": registry.counts(),
        }

    @mcp.tool()
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
        """Rank tenant-owned AI entries with operational-state gating."""
        registry = tenant_ai_registry()
        request = MatchRequest(
            task=task,
            category=category,
            required_capabilities=required_capabilities or [],
            input_modality=input_modality,
            output_modality=output_modality,
            prefer_free=prefer_free,
            operational_only=operational_only,
            limit=limit,
        )
        return {"matches": registry.match(request), "counts": registry.counts()}

    @mcp.tool()
    def seed_ai_catalog() -> dict:
        """Seed the curated catalogue into this tenant without overwriting operator edits."""
        return seed_catalog_records(tenant_ai_registry())

    @mcp.tool()
    async def execute_ai_task(
        task: str,
        category: str | None = None,
        limit: int = 3,
    ) -> dict:
        """Match and run only configured tenant models with usable connectors."""
        if not 1 <= limit <= 10:
            return {"ok": False, "error": "limit_must_be_between_1_and_10"}
        ai_registry = tenant_ai_registry()
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
        selected_ids = [
            item["model_id"] for item in matches
            if item["model_id"] in adapters
        ]
        skipped = [
            {
                "model_id": item["model_id"],
                "reason": "connector_or_credentials_not_configured",
            }
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
        runnable_registry = AIRegistry(
            model for model in models if model.id in selected_ids
        )
        manager = AIExecutionManager(
            runnable_registry,
            {model_id: adapters[model_id] for model_id in selected_ids},
            max_parallel=min(3, len(selected_ids)),
            timeout_s=settings.request_timeout,
        )
        results = await manager.execute_parallel(selected_ids, task)
        return {
            "ok": any(item["ok"] for item in results),
            "selected_model_ids": selected_ids,
            "skipped": skipped,
            "results": results,
            "registry_counts": ai_registry.counts(),
        }

    @mcp.tool()
    async def test_ai_connector(model_id: str) -> dict:
        """Explicitly probe a configured connector and save tenant-scoped health."""
        ai_registry = tenant_ai_registry()
        models = ai_registry.list()
        model = next((item for item in models if item.id == model_id), None)
        if model is None:
            return {"ok": False, "error": "model_not_registered"}
        if model.status not in {"configured", "tested", "degraded"}:
            return {
                "ok": False,
                "error": "model_not_operational",
                "status": model.status,
            }
        adapters = build_adapters(
            models,
            default_endpoint=settings.provider_base_url,
            default_api_key=settings.provider_api_key,
        )
        adapter = adapters.get(model_id)
        if adapter is None:
            return {
                "ok": False,
                "error": "connector_or_credentials_not_configured",
            }
        try:
            probe = await smoke_test_adapter(
                adapter, model, timeout_s=min(settings.request_timeout, 20.0)
            )
        except TimeoutError:
            ai_registry.upsert(model.model_copy(update={"status": "degraded"}))
            return {"ok": False, "error": "timeout", "status": "degraded"}
        except Exception as exc:  # noqa: BLE001 - never expose provider bodies or secrets
            ai_registry.upsert(model.model_copy(update={"status": "degraded"}))
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
