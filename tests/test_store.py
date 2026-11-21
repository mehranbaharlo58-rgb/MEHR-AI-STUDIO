import pytest

from mehr_ai_studio.store import StudioStore


def test_memory_round_trip(tmp_path):
    store = StudioStore(tmp_path / "studio.sqlite3")
    saved = store.save_memory("brand.voice", {"tone": "professional"})
    loaded = store.read_memory("brand.voice")
    assert saved["key"] == "brand.voice"
    assert loaded["value"] == {"tone": "professional"}


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
