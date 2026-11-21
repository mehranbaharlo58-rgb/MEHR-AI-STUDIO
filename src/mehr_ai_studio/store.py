"""Small SQLite store for explicit project memory and human feedback."""
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class StudioStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self):
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self):
        with self._connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS memories (
                key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at TEXT NOT NULL
            )""")
            db.execute("""CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_type TEXT NOT NULL, rating INTEGER NOT NULL,
                note TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL
            )""")

    def save_memory(self, key: str, value: Any) -> dict:
        if not isinstance(key, str) or not key.strip():
            raise ValueError("memory key is required")
        key = key.strip()
        try:
            serialized = json.dumps(value, ensure_ascii=False)
        except (TypeError, ValueError) as exc:
            raise ValueError("memory value must be JSON-serializable") from exc
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as db:
            db.execute(
                """INSERT INTO memories(key,value,updated_at) VALUES(?,?,?)
                   ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at""",
                (key, serialized, now),
            )
        return {"key": key, "updated_at": now}

    def read_memory(self, key: str) -> dict | None:
        if not isinstance(key, str):
            raise ValueError("memory key must be a string")
        with self._connect() as db:
            row = db.execute(
                "SELECT key,value,updated_at FROM memories WHERE key=?",
                (key.strip(),),
            ).fetchone()
        if row is None:
            return None
        return {"key": row["key"], "value": json.loads(row["value"]), "updated_at": row["updated_at"]}

    def record_feedback(self, item_type: str, rating: int, note: str = "") -> dict:
        if isinstance(rating, bool) or not isinstance(rating, int) or not 1 <= rating <= 5:
            raise ValueError("rating must be an integer between 1 and 5")
        if not isinstance(item_type, str) or not isinstance(note, str):
            raise ValueError("item_type and note must be strings")
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as db:
            cursor = db.execute(
                "INSERT INTO feedback(item_type,rating,note,created_at) VALUES(?,?,?,?)",
                (item_type.strip() or "general", rating, note.strip(), now),
            )
            feedback_id = cursor.lastrowid
        return {"id": feedback_id, "rating": rating, "created_at": now}

    def feedback_insights(self) -> dict:
        with self._connect() as db:
            row = db.execute(
                "SELECT COUNT(*) AS count, AVG(rating) AS average FROM feedback"
            ).fetchone()
            by_type = db.execute(
                "SELECT item_type, COUNT(*) AS count, AVG(rating) AS average "
                "FROM feedback GROUP BY item_type ORDER BY count DESC"
            ).fetchall()
        return {
            "feedback_count": row["count"],
            "average_rating": round(row["average"], 2) if row["average"] is not None else None,
            "by_type": [
                {"item_type": item["item_type"], "count": item["count"],
                 "average_rating": round(item["average"], 2)}
                for item in by_type
            ],
            "note": "Feedback is stored for analysis; it does not train or fine-tune a model.",
        }
