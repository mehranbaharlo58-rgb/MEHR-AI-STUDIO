"""Load the curated AI catalogue without overwriting operator configuration."""
from __future__ import annotations

import json
from importlib.resources import files

from .ai_registry_store import AIRegistryStore
from .ai_stack import AIModel


def seed_ai_catalog(store: AIRegistryStore) -> dict[str, int]:
    """Insert missing catalogue records; preserve all existing operator-edited records."""
    resource = files("mehr_ai_studio").joinpath("data/ai_catalog_seed.json")
    records = json.loads(resource.read_text(encoding="utf-8"))
    existing = {model.id for model in store.list()}
    added = 0
    for record in records:
        model = AIModel.model_validate(record)
        if model.id not in existing:
            store.upsert(model)
            existing.add(model.id)
            added += 1
    return {"catalog_entries": len(records), "added": added, "already_present": len(records) - added}
