"""Deterministic content-brief and structural quality primitives."""
import re
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
    if any(not isinstance(value, str) for value in required.values()):
        raise TypeError("goal, audience, and channel must be strings")
    if any(not value.strip() for value in required.values()):
        raise ValueError("goal, audience, and channel must be non-empty")
    if not isinstance(language, str) or not isinstance(tone, str):
        raise TypeError("language and tone must be strings")
    if key_points is not None and not isinstance(key_points, list):
        raise TypeError("key_points must be a list of strings")
    if key_points is not None and any(
        not isinstance(point, str) for point in key_points
    ):
        raise TypeError("key_points must contain only strings")
    if key_points is not None and any(not point.strip() for point in key_points):
        raise ValueError("key_points cannot contain empty strings")

    return ContentBrief(
        goal.strip(),
        audience.strip(),
        channel.strip(),
        language.strip() or "Persian",
        tone.strip() or "clear and professional",
        key_points or [],
    ).to_dict()


def assess_text(text: str) -> dict[str, Any]:
    """Return explainable structural scores; never infer factual or semantic quality."""
    if not isinstance(text, str):
        raise TypeError("text must be a string")

    content = text.strip()
    words = content.split()
    sentences = [
        part.strip()
        for part in re.split(r"[.!?؟۔]+", content)
        if part.strip()
    ]
    lines = [line.strip() for line in content.splitlines() if line.strip()]
    bullets = [
        line for line in lines
        if re.match(r"^(?:[-*•]|\d+[.)])\s+", line)
    ]
    paragraphs = [part for part in re.split(r"\n\s*\n", content) if part.strip()]
    word_count = len(words)
    sentence_count = len(sentences)
    average_sentence_length = (
        round(word_count / sentence_count, 1) if sentence_count else 0.0
    )

    checks = {
        "non_empty": bool(content),
        "has_sentence_or_bullet": bool(sentences or bullets),
        "word_count": word_count,
        "sentence_count": sentence_count,
        "paragraph_count": len(paragraphs),
        "bullet_count": len(bullets),
        "average_sentence_length": average_sentence_length,
    }

    dimensions = {
        "completeness": 100 if content else 0,
        "structure": 100 if sentences or bullets else (50 if paragraphs else 0),
        "length": (
            0 if word_count == 0
            else min(100, round(word_count * 100 / 30))
            if word_count < 30
            else max(0, 100 - round((word_count - 500) * 100 / 500))
            if word_count > 500
            else 100
        ),
        "readability": (
            0 if word_count == 0
            else 100 if average_sentence_length <= 25
            else max(0, 100 - round((average_sentence_length - 25) * 3))
        ),
    }
    score = round(sum(dimensions.values()) / len(dimensions))

    return {
        "score": score,
        "dimensions": dimensions,
        "checks": checks,
        "limitations": [
            "Structural heuristics only; no semantic or brief-adherence evaluation.",
            "Does not verify factual accuracy, sources, originality, or legal compliance.",
        ],
    }
