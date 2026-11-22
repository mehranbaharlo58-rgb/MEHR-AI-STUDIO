"""Offline installation and core-function smoke check.

Run with: python -m mehr_ai_studio.selfcheck
This check requires no API key, network access, or hosted identity provider.
"""
import json
import tempfile
from pathlib import Path

from . import __version__
from .core import assess_text, build_content_brief
from .store import StudioStore


def run_self_check() -> dict:
    checks = {}
    with tempfile.TemporaryDirectory(prefix="mehr-ai-studio-") as directory:
        db_path = Path(directory) / "smoke.sqlite3"
        store = StudioStore(db_path)
        saved = store.save_memory("selfcheck", {"ready": True})
        loaded = store.read_memory("selfcheck")
        checks["sqlite_write_read"] = bool(
            saved["key"] == "selfcheck"
            and loaded
            and loaded["value"] == {"ready": True}
        )

    brief = build_content_brief(
        "Create a useful product introduction",
        "small business owners",
        "website",
    )
    checks["content_brief"] = (
        brief["goal"] == "Create a useful product introduction"
        and brief["audience"] == "small business owners"
    )
    assessment = assess_text(
        "This is a short structural assessment example with enough words to verify the core pipeline."
    )
    checks["content_assessment"] = (
        assessment["checks"]["non_empty"] is True
        and assessment["score"] > 0
    )
    return {
        "name": "MEHR AI STUDIO",
        "version": __version__,
        "ok": all(checks.values()),
        "checks": checks,
        "provider_tested": False,
        "network_required": False,
    }


def main() -> None:
    result = run_self_check()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["ok"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
