"""Provider-independent AI registry, matching, and bounded parallel dispatch."""
from __future__ import annotations

import asyncio
import re
import time
from collections.abc import Awaitable, Callable, Iterable
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

AIStatus = Literal["catalog_only", "configured", "tested", "degraded", "disabled"]
AccessMode = Literal["native_api", "openai_compatible", "local_runtime", "mcp", "web_app", "sdk"]
Availability = Literal["free", "freemium", "paid", "local", "unknown"]
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
    website_url: str | None = Field(default=None, max_length=1000)
    docs_url: str | None = Field(default=None, max_length=1000)
    source_urls: list[str] = Field(default_factory=list, max_length=10)
    verification_status: Literal["unverified", "source_checked", "api_checked", "integration_tested"] = "unverified"
    last_verified_at: str | None = Field(default=None, max_length=40)

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



_TASK_ALIASES = {
    "تحقیق": {"research", "search", "literature-review", "papers"},
    "پژوهش": {"research", "search", "literature-review", "papers"},
    "کدنویسی": {"coding", "code", "software", "debugging"},
    "برنامه‌نویسی": {"coding", "code", "software", "debugging"},
    "برنامه نویسی": {"coding", "code", "software", "debugging"},
    "تولید تصویر": {"image", "image-generation", "design"},
    "تصویر": {"image", "image-generation"},
    "ویدئو": {"video", "video-generation"},
    "ویدیو": {"video", "video-generation"},
    "صدا": {"audio", "voice", "speech"},
    "گویندگی": {"audio", "voice", "text-to-speech"},
    "ترجمه": {"translation", "multilingual"},
    "خلاصه": {"summarization", "summary", "documents"},
    "خلاصه‌سازی": {"summarization", "summary", "documents"},
    "تحلیل": {"analysis", "reasoning"},
    "اسناد": {"documents", "document-parsing", "pdf"},
    "سند": {"documents", "document-parsing", "pdf"},
    "اتوماسیون": {"automation", "workflow", "integrations"},
    "عامل": {"agents", "orchestration", "tools"},
    "ایجنت": {"agents", "orchestration", "tools"},
    "پایگاه": {"database", "vectors", "retrieval"},
    "برداری": {"vectors", "vector-search", "retrieval"},
}


def _task_terms(text: str) -> set[str]:
    normalized = text.lower().replace("ي", "ی").replace("ك", "ک")
    terms = set(re.findall(r"[a-z0-9_]+|[\u0600-\u06ff]+", normalized))
    expanded = set(terms)
    for phrase, aliases in _TASK_ALIASES.items():
        if phrase in normalized:
            expanded.update(aliases)
    for term in tuple(terms):
        expanded.update(_TASK_ALIASES.get(term, set()))
    return expanded


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
        task_terms = _task_terms(request.task)
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
    """Dispatch up to 100 selected models with global, provider, and model limits."""

    def __init__(
        self,
        registry: AIRegistry,
        adapters: dict[str, Adapter],
        max_parallel: int = 10,
        timeout_s: float = 90.0,
        provider_limits: dict[str, int] | None = None,
    ) -> None:
        if max_parallel < 1 or max_parallel > 100:
            raise ValueError("max_parallel must be between 1 and 100")
        if timeout_s <= 0:
            raise ValueError("timeout_s must be positive")
        self.registry, self.adapters = registry, adapters
        self.timeout_s = timeout_s
        self._global_limit = asyncio.Semaphore(max_parallel)
        self._model_limits: dict[str, asyncio.Semaphore] = {}
        self._provider_limits: dict[str, asyncio.Semaphore] = {}
        self._provider_limit_values = provider_limits or {}
        if any(value < 1 or value > 100 for value in self._provider_limit_values.values()):
            raise ValueError("provider limits must be between 1 and 100")

    async def _execute_one(self, model_id: str, task: str) -> dict[str, Any]:
        model = self.registry.get(model_id)
        if model is None:
            return {"model_id": model_id, "ok": False, "error": "model_not_registered"}
        if model.status not in {"configured", "tested"}:
            return {"model_id": model_id, "ok": False, "error": "model_not_operational"}
        adapter = self.adapters.get(model_id)
        if adapter is None:
            return {"model_id": model_id, "ok": False, "error": "adapter_not_registered"}

        model_limit = self._model_limits.setdefault(
            model_id, asyncio.Semaphore(model.max_concurrency)
        )
        provider_limit_value = self._provider_limit_values.get(model.provider, 10)
        provider_limit = self._provider_limits.setdefault(
            model.provider, asyncio.Semaphore(provider_limit_value)
        )
        started = time.perf_counter()
        try:
            async with self._global_limit, provider_limit, model_limit:
                result = await asyncio.wait_for(adapter(model, task), timeout=self.timeout_s)
            return {
                "model_id": model_id,
                "ok": True,
                "result": result,
                "latency_ms": round((time.perf_counter() - started) * 1000, 2),
            }
        except TimeoutError:
            return {
                "model_id": model_id,
                "ok": False,
                "error": "timeout",
                "latency_ms": round((time.perf_counter() - started) * 1000, 2),
            }
        except Exception as exc:  # noqa: BLE001 - isolate arbitrary adapter/provider failures
            return {
                "model_id": model_id,
                "ok": False,
                "error": type(exc).__name__,
                "latency_ms": round((time.perf_counter() - started) * 1000, 2),
            }

    async def execute_parallel(self, model_ids: list[str], task: str) -> list[dict[str, Any]]:
        if not task.strip():
            raise ValueError("task must be non-empty")
        if not model_ids or len(model_ids) > 100:
            raise ValueError("dispatch batch must contain between 1 and 100 models")
        if len(set(model_ids)) != len(model_ids):
            raise ValueError("model_ids must be unique")
        return await asyncio.gather(*(self._execute_one(item, task) for item in model_ids))
