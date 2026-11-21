from mehr_ai_studio import workflow
from mehr_ai_studio.store import StudioStore


def test_workflow_loads_memory_generates_and_assesses(tmp_path, monkeypatch):
    store = StudioStore(tmp_path / "studio.sqlite3")
    store.save_memory("brand", {"voice": "professional"})
    monkeypatch.setattr(
        workflow,
        "generate_text",
        lambda prompt: {"text": "This is a sufficiently useful generated content sample. " * 5, "model": "test"},
    )

    result = workflow.run_content_workflow(
        store, "Explain a service", "small businesses", "website"
    )

    assert result["ok"] is True
    assert result["context_loaded"] is True
    assert result["generated"]["model"] == "test"
    assert result["assessment"]["score"] == 100


def test_workflow_reports_missing_provider(tmp_path, monkeypatch):
    store = StudioStore(tmp_path / "studio.sqlite3")

    def no_provider(prompt):
        raise workflow.ProviderNotConfigured("configure provider")

    monkeypatch.setattr(workflow, "generate_text", no_provider)
    result = workflow.run_content_workflow(
        store, "Explain a service", "small businesses", "website"
    )

    assert result["ok"] is False
    assert result["error"] == "provider_not_configured"
    assert result["brief"]["goal"] == "Explain a service"
