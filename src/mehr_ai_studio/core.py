"""Deterministic content-brief and structural quality primitives."""
from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class ContentBrief:
    goal: str
    audience: str
    channel: str
    language: str = "Persian"
    tone: str = "clear and professional"
    key_points: list[str] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_content_brief(
    goal: str,
    audience: str,
    channel: str,
    language: str = "Persian",
    tone: str = "clear and professional",
    key_points: list[str] | None = None,
) -> dict[str, Any]:
    required = {"goal": goal, "audience": audience, "channel": channel}
    if any(not isinstance(value, str) or not value.strip() for value in required.values()):
        raise ValueError("goal, audience, and channel must be non-empty strings")
    if not isinstance(language, str) or not isinstance(tone, str):
        raise ValueError("language and tone must be strings")
    if key_points is not None and (
        not isinstance(key_points, list)
        or any(not isinstance(point, str) or not point.strip() for point in key_points)
    ):
        raise ValueError("key_points must be a list of non-empty strings")

    return ContentBrief(
        goal.strip(),
        audience.strip(),
        channel.strip(),
        language.strip() or "Persian",
        tone.strip() or "clear and professional",
        key_points or [],
    ).to_dict()


def assess_text(text: str) -> dict[str, Any]:
    """Structural checks only; does not establish factual accuracy."""
    if not isinstance(text, str):
        raise ValueError("text must be a string")
    content = text.strip()
    words = content.split()
    checks = {
        "non_empty": bool(content),
        "has_sentence_or_bullet": any(mark in content for mark in (".", "!", "?", "\n", "-")),
        "word_count": len(words),
    }
    score = (40 if checks["non_empty"] else 0) + (20 if checks["has_sentence_or_bullet"] else 0)
    score += 40 if len(words) >= 30 else round(40 * len(words) / 30)
    return {
        "score": score,
        "checks": checks,
        "limitations": ["Does not verify factual accuracy or originality."],
    }
