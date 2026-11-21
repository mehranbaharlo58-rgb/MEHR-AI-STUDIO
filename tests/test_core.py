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

def test_assess_text_empty():
    result = assess_text("")
    assert result["score"] == 0
    assert result["checks"]["non_empty"] is False

def test_assess_text_nonempty():
    result = assess_text("This is a short test.")
    assert result["score"] > 0
    assert result["checks"]["non_empty"] is True
