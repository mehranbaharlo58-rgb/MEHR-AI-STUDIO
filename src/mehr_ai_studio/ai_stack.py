"""Provider-independent AI registry, matching, and bounded parallel dispatch."""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Iterable
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

AIStatus = Literal["catalog_only", "configured", "tested", "degraded", "disabled"]
AccessMode = Literal["native_api", "openai_compatible", "local_runtime", "mcp", "web_app"]
Availability = Literal["free", "freemium", "paid", "local"]
Modality = Literal["text", "image", "audio", "video", "code", "structured_data"]


class AIModel(BaseModel):
    """One AI model, tool, or service in the unified catalogue."""
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    id: str = Field(min_length=2, max_length=120, pattern=r"^[a-zA-Z0-9][a-zA-Z0-9._:-]*$")
    name: str = Field(min_length=1, max_length=160)
    provider: str = Field(min_length=1, max_length=120)
    category: str = Field(min_length=2, max_length=80)
    capabilities: list[str] = Field(default_factory=list, max_length=80)
    task_tags: list[str] = Field(default_factory=list, max_length=100)
    input_modalities: list[Modality] = Field(default_factory=lambda: ["text"], max_length=6)
    output_modalities: list[Modality] = Field(default_factory=lambda: ["text"], max_length=6)
    access_mode: AccessMode
    availability: Availability
    status: AIStatus = "catalog_only"
    model_id: str | None = Field(default=None, max_length=200)
    endpoint: str | None = Field(default=None, max_length=1000)
    auth_required: bool = True
    max_concurrency: int = Field(default=1, ge=1, le=1000)
    quality_score: float | None = Field(default=None, ge=0, le=100)
    latency_ms: int | None = Field(default=None, ge=1, le=600000)
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("capabilities", "task_tags")
    @classmethod
    def normalize_terms(cls, values: list[str]) -> list[str]:
        result, seen = [], set()
        for value in values:
            term = value.strip().lower()
            if not term:
                raise ValueError("capabilities and task tags cannot be empty")
            if term not in seen:
                result.append(term)
                seen.add(term)
        return result


class MatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    task: str = Field(min_length=2, max_length=4000)
    category: str | None = Field(default=None, max_length=80)
    required_capabilities: list[str] = Field(default_factory=list, max_length=30)
    input_modality: Modality = "text"
    output_modality: Modality = "text"
    prefer_free: bool = True
    operational_only: bool = True
    limit: int = Field(default=10, ge=1, le=100)


class MatchResult(BaseModel):
    model_id: str
    name: str
    provider: str
    score: float = Field(ge=0, le=100)
    status: AIStatus
    reasons: list[str]


class AIRegistry:
    """In-memory registry interface; durable storage is a separate concern."""
    def __init__(self, models: Iterable[AIModel] = ()) -> None:
        self._models: dict[str, AIModel] = {}
        for model in models:
            self.upsert(model)

    def upsert(self, model: AIModel) -> None:
        self._models[model.id] = model

    def get(self, model_id: str) -> AIModel | None:
        return self._models.get(model_id)

    def list(self, *, status: AIStatus | None = None, category: str | None = None) -> list[AIModel]:
        values = self._models.values()
        if status:
            values = (item for item in values if item.status == status)
        if category:
            values = (item for item in values if item.category.lower() == category.strip().lower())
        return sorted(values, key=lambda item: (item.category, item.provider, item.name))

    def match(self, request: MatchRequest) -> list[MatchResult]:
        task_terms = set(request.task.lower().replace("/", " ").replace("-", " ").split())
        required = {term.strip().lower() for term in request.required_capabilities}
        results = []
        for model in self._models.values():
            if model.status == "disabled":
                continue
            if request.operational_only and model.status not in {"configured", "tested"}:
                continue
            if request.input_modality not in model.input_modalities:
                continue
            if request.output_modality not in model.output_modalities:
                continue
            if required and not required.issubset(set(model.capabilities)):
                continue

            reasons, score = [], 35.0
            if request.category and model.category.lower() == request.category.lower():
                score += 25
                reasons.append("category_match")
            elif request.category:
                score -= 8
            if required:
                score += 25
                reasons.append("required_capabilities_match")
            matched = task_terms & set(model.task_tags)
            if matched:
                score += min(20, 5 * len(matched))
                reasons.append("task_tag_match:" + ",".join(sorted(matched)))
            if request.prefer_free and model.availability in {"free", "local"}:
                score += 10
                reasons.append("free_or_local_preference")
            if model.status == "tested":
                score += 8
                reasons.append("integration_tested")
            elif model.status == "configured":
                reasons.append("configured_not_live_tested")
            if model.quality_score is not None:
                score += (model.quality_score - 50) * 0.12
                reasons.append("quality_score_available")
            if model.latency_ms is not None:
                score += max(-5, 5 - model.latency_ms / 1000)
                reasons.append("latency_measurement_available")
            results.append(MatchResult(
                model_id=model.id, name=model.name, provider=model.provider,
                score=round(max(0, min(100, score)), 2), status=model.status,
                reasons=reasons or ["baseline_compatible_candidate"],
            ))
        return sorted(results, key=lambda item: (-item.score, item.model_id))[:request.limit]


Adapter = Callable[[AIModel, str], Awaitable[dict[str, Any]]]


class AIExecutionManager:
    """Bounded parallel dispatcher with per-model limits and failure isolation."""
    def __init__(self, registry: AIRegistry, adapters: dict[str, Adapter], max_parallel: int = 10):
        if max_parallel < 1:
            raise ValueError("max_parallel must be at least 1")
        self.registry, self.adapters = registry, adapters
        self._global_limit = asyncio.Semaphore(max_parallel)
        self._model_limits: dict[str, asyncio.Semaphore] = {}

    async def _execute_one(self, model_id: str, task: str) -> dict[str, Any]:
        model = self.registry.get(model_id)
        if model is None:
            return {"model_id": model_id, "ok": False, "error": "model_not_registered"}
        if model.status not in {"configured", "tested"}:
            return {"model_id": model_id, "ok": False, "error": "model_not_operational"}
        adapter = self.adapters.get(model_id)
        if adapter is None:
            return {"model_id": model_id, "ok": False, "error": "adapter_not_registered"}
        limit = self._model_limits.setdefault(model_id, asyncio.Semaphore(model.max_concurrency))
        async with self._global_limit, limit:
            try:
                return {"model_id": model_id, "ok": True, "result": await adapter(model, task)}
            except Exception as exc:  # noqa: BLE001 - isolate arbitrary adapter/provider failures
                return {"model_id": model_id, "ok": False, "error": type(exc).__name__}

    async def execute_parallel(self, model_ids: list[str], task: str) -> list[dict[str, Any]]:
        if not task.strip():
            raise ValueError("task must be non-empty")
        if not model_ids or len(model_ids) > 100:
            raise ValueError("dispatch batch must contain between 1 and 100 models")
        if len(set(model_ids)) != len(model_ids):
            raise ValueError("model_ids must be unique")
        return await asyncio.gather(*(self._execute_one(item, task) for item in model_ids))
