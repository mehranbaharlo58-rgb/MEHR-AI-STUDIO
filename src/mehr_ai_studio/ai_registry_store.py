"""Tenant-scoped SQLite persistence for the universal AI registry."""
from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from .ai_stack import AIModel, AIRegistry, MatchRequest


class AIRegistryStore:
    def __init__(self, path: str | Path, tenant_id: str = "default"):
        self.path = Path(path)
        self.tenant_id = tenant_id.strip()
        if not self.tenant_id or len(self.tenant_id) > 128:
            raise ValueError("invalid tenant_id")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS ai_registry (
                tenant_id TEXT NOT NULL, model_id TEXT NOT NULL,
                payload TEXT NOT NULL, updated_at TEXT NOT NULL,
                PRIMARY KEY (tenant_id, model_id))""")
            db.execute("CREATE INDEX IF NOT EXISTS idx_ai_registry_tenant ON ai_registry(tenant_id)")

    def _connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        return db

    def upsert(self, model: AIModel) -> dict:
        now = datetime.now(UTC).isoformat()
        with self._connect() as db:
            db.execute("""INSERT INTO ai_registry(tenant_id,model_id,payload,updated_at)
                VALUES(?,?,?,?) ON CONFLICT(tenant_id,model_id) DO UPDATE SET
                payload=excluded.payload, updated_at=excluded.updated_at""",
                (self.tenant_id, model.id, model.model_dump_json(), now))
        return {"saved": True, "model_id": model.id, "updated_at": now}

    def list(self, status: str | None = None, category: str | None = None) -> list[AIModel]:
        with self._connect() as db:
            rows = db.execute("SELECT payload FROM ai_registry WHERE tenant_id=? ORDER BY model_id",
                (self.tenant_id,)).fetchall()
        return AIRegistry(AIModel.model_validate_json(row["payload"]) for row in rows).list(
            status=status, category=category)

    def match(self, request: MatchRequest) -> list[dict]:
        return [item.model_dump() for item in AIRegistry(self.list()).match(request)]

    def counts(self) -> dict[str, int]:
        counts = {key: 0 for key in ("catalog_only", "configured", "tested", "degraded", "disabled")}
        for model in self.list():
            counts[model.status] += 1
        counts["total"] = sum(counts.values())
        return counts
