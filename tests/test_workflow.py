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
    saved_run = store.read_workflow_run(result["run_id"], "default")
    assert saved_run["status"] == "succeeded"
    assert saved_run["result"]["generated"]["model"] == "test"


def test_workflow_uses_only_requested_tenant_memory(tmp_path, monkeypatch):
    store = StudioStore(tmp_path / "studio.sqlite3")
    store.save_memory("brand", {"voice": "Alpha"}, tenant_id="alpha")
    store.save_memory("brand", {"voice": "Beta"}, tenant_id="beta")
    captured = {}

    def fake_generate(prompt):
        captured["prompt"] = prompt
        return {"text": "A sufficiently useful generated content sample. " * 5, "model": "test"}

    monkeypatch.setattr(workflow, "generate_text", fake_generate)
    result = workflow.run_content_workflow(
        store, "Explain a service", "small businesses", "website", tenant_id="alpha"
    )

    assert result["context_loaded"] is True
    assert "Alpha" in captured["prompt"]
    assert "Beta" not in captured["prompt"]


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
    assert store.read_workflow_run(result["run_id"], "default")["status"] == "failed"


def test_workflow_returns_contract_normalized_asset_and_report(tmp_path, monkeypatch):
    store = StudioStore(tmp_path / "studio.sqlite3")
    monkeypatch.setattr(
        workflow,
        "generate_text",
        lambda prompt: {"text": "A validated generated content sample. " * 5, "model": "test-model"},
    )

    result = workflow.run_content_workflow(
        store, "Explain a service", "small businesses", "website"
    )

    assert result["generated"] == {
        "text": "A validated generated content sample. " * 5,
        "model": "test-model",
        "format": "text",
    }
    assert 0 <= result["assessment"]["score"] <= 100
    assert result["assessment"]["checks"]["non_empty"] is True


def test_workflow_marks_malformed_provider_contract_failed(tmp_path, monkeypatch):
    store = StudioStore(tmp_path / "studio.sqlite3")
    monkeypatch.setattr(
        workflow, "generate_text", lambda prompt: {"text": "", "model": "test-model"}
    )

    result = workflow.run_content_workflow(
        store, "Explain a service", "small businesses", "website"
    )

    assert result["ok"] is False
    assert result["error"] == "invalid_provider_response"
    saved_run = store.read_workflow_run(result["run_id"], "default")
    assert saved_run["status"] == "failed"
    assert saved_run["error_code"] == "invalid_provider_response"
