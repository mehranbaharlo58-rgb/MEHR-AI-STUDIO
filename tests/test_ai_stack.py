"""Tests for AI registry matching and execution scheduling."""
import asyncio

import pytest
from pydantic import ValidationError

from mehr_ai_studio.ai_stack import (
    AIExecutionManager,
    AIModel,
    AIRegistry,
    MatchRequest,
)


def entry(**changes):
    data = {"id": "local.llama", "name": "Local Llama", "provider": "Ollama",
        "category": "reasoning", "capabilities": ["reasoning", "summarization"],
        "task_tags": ["analysis", "research"], "input_modalities": ["text"],
        "output_modalities": ["text"], "access_mode": "local_runtime",
        "availability": "local", "status": "tested", "max_concurrency": 1,
        "quality_score": 80, "latency_ms": 900}
    data.update(changes)
    return AIModel(**data)


def test_matcher_ranks_operational_models_and_explains_match():
    registry = AIRegistry([entry(), entry(id="catalog.img", name="Image",
        category="image", capabilities=["image-generation"],
        output_modalities=["image"], access_mode="web_app",
        availability="freemium", status="catalog_only")])
    result = registry.match(MatchRequest(task="research analysis",
        category="reasoning", required_capabilities=["reasoning"]))
    assert len(result) == 1
    assert result[0].model_id == "local.llama"
    assert "integration_tested" in result[0].reasons


def test_catalog_only_is_excluded_from_operational_matching():
    registry = AIRegistry([entry(status="catalog_only")])
    assert registry.match(MatchRequest(task="research")) == []
    assert len(registry.match(MatchRequest(task="research",
        operational_only=False))) == 1


def test_contract_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        entry(unexpected_field=True)


def test_upsert_and_filter():
    registry = AIRegistry([entry()])
    registry.upsert(entry(name="Updated"))
    assert len(registry.list(status="tested", category="reasoning")) == 1
    assert registry.get("local.llama").name == "Updated"


def test_parallel_dispatch_is_bounded_and_isolates_provider_failure():
    async def run():
        registry = AIRegistry([entry(id=f"m{i}", name=f"Model {i}") for i in range(4)])
        active, peak = 0, 0
        async def adapter(model, task):
            nonlocal active, peak
            active += 1
            peak = max(peak, active)
            await asyncio.sleep(.01)
            active -= 1
            if model.id == "m2":
                raise RuntimeError("unavailable")
            return {"text": task}
        manager = AIExecutionManager(registry,
            {f"m{i}": adapter for i in range(4)}, max_parallel=2)
        results = await manager.execute_parallel([f"m{i}" for i in range(4)], "hello")
        assert peak <= 2
        assert sum(item["ok"] for item in results) == 3
        assert results[2]["error"] == "RuntimeError"
    asyncio.run(run())


def test_dispatch_rejects_duplicate_or_over_100_models():
    manager = AIExecutionManager(AIRegistry([entry()]), {})
    with pytest.raises(ValueError):
        asyncio.run(manager.execute_parallel(["local.llama"] * 2, "task"))
    with pytest.raises(ValueError):
        asyncio.run(manager.execute_parallel(["x"] * 101, "task"))
