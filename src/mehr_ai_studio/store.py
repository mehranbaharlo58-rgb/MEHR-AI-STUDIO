"""SQLite store for tenant-scoped project memory and human feedback."""

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DEFAULT_TENANT_ID = "default"


def validate_tenant_id(tenant_id: str) -> str:
    if not isinstance(tenant_id, str):
        raise TypeError("tenant_id must be a string")
    tenant_id = tenant_id.strip()
    if not tenant_id:
        raise ValueError("tenant_id is required")
    if len(tenant_id) > 128:
        raise ValueError("tenant_id must be at most 128 characters")
    return tenant_id


class StudioStore:
    """Tenant-aware persistence.

    Tenant IDs must come from a trusted, authenticated server-side identity.
    The default value preserves the original single-user/local behavior; it is
    not an authentication mechanism or a production multi-tenant boundary.
    """

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
            db.execute(
                """CREATE TABLE IF NOT EXISTS memories (
                    tenant_id TEXT NOT NULL DEFAULT 'default',
                    key TEXT NOT NULL,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (tenant_id, key)
                )"""
            )
            memory_columns = {
                row["name"] for row in db.execute("PRAGMA table_info(memories)")
            }
            memory_pk = [
                row["name"]
                for row in sorted(
                    (row for row in db.execute("PRAGMA table_info(memories)") if row["pk"]),
                    key=lambda row: row["pk"],
                )
            ]
            if "tenant_id" not in memory_columns or memory_pk != ["tenant_id", "key"]:
                db.execute(
                    """CREATE TABLE memories_new (
                        tenant_id TEXT NOT NULL DEFAULT 'default',
                        key TEXT NOT NULL,
                        value TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        PRIMARY KEY (tenant_id, key)
                    )"""
                )
                if "tenant_id" in memory_columns:
                    db.execute(
                        """INSERT INTO memories_new(tenant_id,key,value,updated_at)
                           SELECT tenant_id,key,value,updated_at FROM memories"""
                    )
                else:
                    db.execute(
                        """INSERT INTO memories_new(tenant_id,key,value,updated_at)
                           SELECT 'default',key,value,updated_at FROM memories"""
                    )
                db.execute("DROP TABLE memories")
                db.execute("ALTER TABLE memories_new RENAME TO memories")

            db.execute(
                """CREATE TABLE IF NOT EXISTS feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tenant_id TEXT NOT NULL DEFAULT 'default',
                    item_type TEXT NOT NULL,
                    rating INTEGER NOT NULL,
                    note TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL
                )"""
            )
            feedback_columns = {
                row["name"] for row in db.execute("PRAGMA table_info(feedback)")
            }
            if "tenant_id" not in feedback_columns:
                db.execute(
                    "ALTER TABLE feedback ADD COLUMN tenant_id TEXT NOT NULL DEFAULT 'default'"
                )
            db.execute(
                "CREATE INDEX IF NOT EXISTS idx_feedback_tenant_created "
                "ON feedback(tenant_id, created_at)"
            )

    def save_memory(
        self, key: str, value: Any, tenant_id: str = DEFAULT_TENANT_ID
    ) -> dict:
        tenant_id = validate_tenant_id(tenant_id)
        if not isinstance(key, str):
            raise TypeError("memory key must be a string")
        if not key.strip():
            raise ValueError("memory key is required")
        key = key.strip()
        try:
            serialized = json.dumps(value, ensure_ascii=False)
        except (TypeError, ValueError) as exc:
            raise ValueError("memory value must be JSON-serializable") from exc
        now = datetime.now(UTC).isoformat()
        with self._connect() as db:
            db.execute(
                """INSERT INTO memories(tenant_id,key,value,updated_at)
                   VALUES(?,?,?,?)
                   ON CONFLICT(tenant_id,key) DO UPDATE SET
                   value=excluded.value, updated_at=excluded.updated_at""",
                (tenant_id, key, serialized, now),
            )
        return {"tenant_id": tenant_id, "key": key, "updated_at": now}

    def read_memory(
        self, key: str, tenant_id: str = DEFAULT_TENANT_ID
    ) -> dict | None:
        tenant_id = _validate_tenant_id(tenant_id)
        if not isinstance(key, str):
            raise TypeError("memory key must be a string")
        with self._connect() as db:
            row = db.execute(
                """SELECT key,value,updated_at FROM memories
                   WHERE tenant_id=? AND key=?""",
                (tenant_id, key.strip()),
            ).fetchone()
        if row is None:
            return None
        return {
            "tenant_id": tenant_id,
            "key": row["key"],
            "value": json.loads(row["value"]),
            "updated_at": row["updated_at"],
        }

    def record_feedback(
        self,
        item_type: str,
        rating: int,
        note: str = "",
        tenant_id: str = DEFAULT_TENANT_ID,
    ) -> dict:
        tenant_id = _validate_tenant_id(tenant_id)
        if isinstance(rating, bool) or not isinstance(rating, int) or not 1 <= rating <= 5:
            raise ValueError("rating must be an integer between 1 and 5")
        if not isinstance(item_type, str) or not isinstance(note, str):
            raise TypeError("item_type and note must be strings")
        now = datetime.now(UTC).isoformat()
        with self._connect() as db:
            cursor = db.execute(
                """INSERT INTO feedback(tenant_id,item_type,rating,note,created_at)
                   VALUES(?,?,?,?,?)""",
                (tenant_id, item_type.strip() or "general", rating, note.strip(), now),
            )
            feedback_id = cursor.lastrowid
        return {
            "id": feedback_id,
            "tenant_id": tenant_id,
            "rating": rating,
            "created_at": now,
        }

    def feedback_insights(self, tenant_id: str = DEFAULT_TENANT_ID) -> dict:
        tenant_id = _validate_tenant_id(tenant_id)
        with self._connect() as db:
            row = db.execute(
                """SELECT COUNT(*) AS count, AVG(rating) AS average
                   FROM feedback WHERE tenant_id=?""",
                (tenant_id,),
            ).fetchone()
            by_type = db.execute(
                """SELECT item_type, COUNT(*) AS count, AVG(rating) AS average
                   FROM feedback WHERE tenant_id=?
                   GROUP BY item_type ORDER BY count DESC""",
                (tenant_id,),
            ).fetchall()
        return {
            "tenant_id": tenant_id,
            "feedback_count": row["count"],
            "average_rating": round(row["average"], 2) if row["average"] is not None else None,
            "by_type": [
                {
                    "item_type": item["item_type"],
                    "count": item["count"],
                    "average_rating": round(item["average"], 2),
                }
                for item in by_type
            ],
            "note": "Feedback is stored for analysis; it does not train or fine-tune a model.",
        }
