import sqlite3

import pytest

from mehr_ai_studio.store import StudioStore


def test_memory_round_trip(tmp_path):
    store = StudioStore(tmp_path / "studio.sqlite3")
    saved = store.save_memory("brand.voice", {"tone": "professional"})
    loaded = store.read_memory("brand.voice")
    assert saved["key"] == "brand.voice"
    assert loaded["value"] == {"tone": "professional"}


def test_memory_isolated_by_tenant(tmp_path):
    store = StudioStore(tmp_path / "studio.sqlite3")
    store.save_memory("brand", {"name": "Alpha"}, tenant_id="alpha")
    store.save_memory("brand", {"name": "Beta"}, tenant_id="beta")
    assert store.read_memory("brand", tenant_id="alpha")["value"] == {"name": "Alpha"}
    assert store.read_memory("brand", tenant_id="beta")["value"] == {"name": "Beta"}
    assert store.read_memory("brand") is None


def test_feedback_isolated_by_tenant(tmp_path):
    store = StudioStore(tmp_path / "studio.sqlite3")
    store.record_feedback("caption", 5, tenant_id="alpha")
    store.record_feedback("caption", 1, tenant_id="beta")
    assert store.feedback_insights("alpha")["average_rating"] == 5
    assert store.feedback_insights("beta")["average_rating"] == 1
    assert store.feedback_insights()["feedback_count"] == 0


def test_legacy_database_migrates_without_losing_data(tmp_path):
    path = tmp_path / "legacy.sqlite3"
    with sqlite3.connect(path) as db:
        db.execute(
            """CREATE TABLE memories (
                key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at TEXT NOT NULL
            )"""
        )
        db.execute(
            """INSERT INTO memories VALUES ('brand', '{"voice":"classic"}', '2026-01-01')"""
        )
        db.execute(
            """CREATE TABLE feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_type TEXT NOT NULL, rating INTEGER NOT NULL,
                note TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL
            )"""
        )
        db.execute(
            """INSERT INTO feedback(item_type,rating,note,created_at)
               VALUES ('caption',4,'good','2026-01-01')"""
        )

    store = StudioStore(path)
    assert store.read_memory("brand")["value"] == {"voice": "classic"}
    assert store.feedback_insights()["feedback_count"] == 1
    store.save_memory("brand", {"voice": "new"}, tenant_id="another")
    assert store.read_memory("brand")["value"] == {"voice": "classic"}
    assert store.read_memory("brand", tenant_id="another")["value"] == {"voice": "new"}


def test_memory_rejects_empty_key(tmp_path):
    store = StudioStore(tmp_path / "studio.sqlite3")
    with pytest.raises(ValueError):
        store.save_memory("  ", "value")


def test_memory_rejects_non_serializable_value(tmp_path):
    store = StudioStore(tmp_path / "studio.sqlite3")
    with pytest.raises(ValueError):
        store.save_memory("bad", object())


def test_feedback_aggregation(tmp_path):
    store = StudioStore(tmp_path / "studio.sqlite3")
    store.record_feedback("caption", 4, "clear")
    store.record_feedback("caption", 2, "too long")
    result = store.feedback_insights()
    assert result["feedback_count"] == 2
    assert result["average_rating"] == 3.0
    assert result["by_type"][0]["item_type"] == "caption"


@pytest.mark.parametrize("rating", [True, False, 0, 6, 2.5, "5"])
def test_feedback_rejects_invalid_rating(tmp_path, rating):
    store = StudioStore(tmp_path / "studio.sqlite3")
    with pytest.raises(ValueError):
        store.record_feedback("caption", rating)


@pytest.mark.parametrize("tenant_id", ["", "   ", "x" * 129, None])
def test_invalid_tenant_id_is_rejected(tmp_path, tenant_id):
    store = StudioStore(tmp_path / "studio.sqlite3")
    with pytest.raises((TypeError, ValueError)):
        store.read_memory("brand", tenant_id=tenant_id)
