from mehr_ai_studio.ai_registry_store import AIRegistryStore
from mehr_ai_studio.catalog import seed_ai_catalog


def test_seed_loads_exactly_100_catalog_only_entries(tmp_path):
    store = AIRegistryStore(tmp_path / "registry.sqlite3")
    result = seed_ai_catalog(store)
    assert result == {"catalog_entries": 100, "added": 100, "already_present": 0}
    assert store.counts()["total"] == 100
    assert store.counts()["catalog_only"] == 100
    assert all(item.verification_status == "unverified" for item in store.list())


def test_seed_is_idempotent_and_preserves_operator_edits(tmp_path):
    store = AIRegistryStore(tmp_path / "registry.sqlite3")
    seed_ai_catalog(store)
    model = store.list()[0]
    store.upsert(model.model_copy(update={"status": "configured", "notes": "operator configured"}))
    result = seed_ai_catalog(store)
    assert result == {"catalog_entries": 100, "added": 0, "already_present": 100}
    saved = store.list(status="configured")
    assert len(saved) == 1
    assert saved[0].notes == "operator configured"
