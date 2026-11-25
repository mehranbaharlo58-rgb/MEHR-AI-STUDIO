import pytest

from mehr_ai_studio.ai_registry_store import AIRegistryStore
from mehr_ai_studio.ai_stack import AIModel, MatchRequest


def item(**changes):
    data = {"id": "local.test", "name": "Local Test", "provider": "Ollama",
        "category": "reasoning", "capabilities": ["reasoning"],
        "task_tags": ["analysis"], "access_mode": "local_runtime",
        "availability": "local", "status": "tested"}
    data.update(changes)
    return AIModel(**data)


def test_registry_store_upserts_lists_matches_and_counts(tmp_path):
    store = AIRegistryStore(tmp_path / "registry.sqlite3")
    store.upsert(item())
    store.upsert(item(name="Renamed"))
    assert store.list()[0].name == "Renamed"
    assert store.counts()["total"] == 1
    assert store.counts()["tested"] == 1
    result = store.match(MatchRequest(task="analysis", category="reasoning"))
    assert result[0]["model_id"] == "local.test"


def test_registry_store_isolates_tenants(tmp_path):
    path = tmp_path / "registry.sqlite3"
    AIRegistryStore(path, "tenant-a").upsert(item())
    assert AIRegistryStore(path, "tenant-b").list() == []
    assert len(AIRegistryStore(path, "tenant-a").list()) == 1


def test_registry_store_rejects_invalid_tenant(tmp_path):
    with pytest.raises(ValueError):
        AIRegistryStore(tmp_path / "registry.sqlite3", " ")
