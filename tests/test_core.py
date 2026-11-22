import pytest

from mehr_ai_studio.core import assess_text, build_content_brief


def test_build_content_brief():
    result = build_content_brief("Explain surveying", "students", "Instagram")
    assert result["goal"] == "Explain surveying"
    assert result["audience"] == "students"
    assert result["channel"] == "Instagram"


def test_build_content_brief_requires_core_fields():
    with pytest.raises(ValueError):
        build_content_brief("", "students", "Instagram")


@pytest.mark.parametrize("bad_value", [None, 123, "   "])
def test_build_content_brief_rejects_invalid_goal(bad_value):
    with pytest.raises((ValueError, TypeError)):
        build_content_brief(bad_value, "students", "Instagram")


def test_build_content_brief_rejects_invalid_key_points():
    with pytest.raises(ValueError):
        build_content_brief("goal", "students", "Instagram", key_points=["ok", " "])


def test_assess_text_empty():
    result = assess_text("")
    assert result["score"] == 0
    assert result["checks"]["non_empty"] is False
    assert set(result["dimensions"]) == {
        "completeness", "structure", "length", "readability"
    }


def test_assess_text_nonempty():
    result = assess_text("This is a short test.")
    assert result["score"] > 0
    assert result["checks"]["non_empty"] is True
    assert result["checks"]["sentence_count"] == 1


def test_assess_text_reports_structure_and_readability_metrics():
    content = "- First clear point.\n- Second clear point.\n\nA final paragraph."
    result = assess_text(content)
    assert result["checks"]["bullet_count"] == 2
    assert result["checks"]["paragraph_count"] == 2
    assert result["dimensions"]["structure"] == 100
    assert result["limitations"]


def test_assess_text_caps_long_content_score():
    result = assess_text("word " * 1100)
    assert result["dimensions"]["length"] == 0
    assert result["score"] <= 75


def test_assess_text_rejects_non_string():
    with pytest.raises(TypeError):
        assess_text(None)
