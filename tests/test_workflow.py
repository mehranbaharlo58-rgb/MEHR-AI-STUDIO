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
    assert saved_run["prompt_version"] == workflow.CONTENT_PROMPT_VERSION
    assert saved_run["model"] == "test"


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
        lambda prompt: {"text": ("A validated generated content sample. " * 5).strip(), "model": "test-model"},
    )

    result = workflow.run_content_workflow(
        store, "Explain a service", "small businesses", "website"
    )

    assert result["generated"] == {
        "text": ("A validated generated content sample. " * 5).strip(),
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


def test_failed_workflow_resumes_from_checkpoint(tmp_path, monkeypatch):
    store = StudioStore(tmp_path / "studio.sqlite3")
    calls = {"count": 0}

    def fail_then_succeed(prompt):
        calls["count"] += 1
        if calls["count"] == 1:
            raise workflow.ProviderError("temporary provider outage")
        return {
            "text": "Resumed content is complete and passes the structural checks. " * 5,
            "model": "test-model",
        }

    monkeypatch.setattr(workflow, "generate_text", fail_then_succeed)
    first = workflow.run_content_workflow(
        store, "Explain a service", "small businesses", "website"
    )
    assert first["ok"] is False
    assert store.read_workflow_run(first["run_id"], "default")["status"] == "failed"

    resumed = workflow.resume_content_workflow(store, first["run_id"])

    assert resumed["ok"] is True
    assert resumed["run_id"] == first["run_id"]
    assert resumed["attempt"] == 2
    saved = store.read_workflow_run(first["run_id"], "default")
    assert saved["status"] == "succeeded"
    assert saved["attempt"] == 2
    assert saved["result"]["brief"]["goal"] == "Explain a service"


def test_workflow_resume_rejects_missing_or_non_failed_run(tmp_path):
    store = StudioStore(tmp_path / "studio.sqlite3")
    missing = workflow.resume_content_workflow(store, "missing-run")
    assert missing["error"] == "run_not_found"

    monkeypatch_run = {
        "run_id": "active-run",
        "status": "running",
        "created_at": "2026-11-22T08:00:00Z",
        "updated_at": "2026-11-22T08:00:00Z",
    }
    store.save_workflow_run(monkeypatch_run, tenant_id="default")
    active = workflow.resume_content_workflow(store, "active-run")
    assert active["error"] == "run_not_resumable"



def test_failed_run_records_prompt_and_configured_model_versions(tmp_path, monkeypatch):
    store = StudioStore(tmp_path / "studio.sqlite3")
    monkeypatch.setattr(workflow, "settings", type("Settings", (), {"provider_model": "configured-model"})())

    def temporary_failure(prompt):
        raise workflow.ProviderError("temporary")

    monkeypatch.setattr(workflow, "generate_text", temporary_failure)
    result = workflow.run_content_workflow(
        store, "Explain a service", "small businesses", "website"
    )
    saved = store.read_workflow_run(result["run_id"], "default")

    assert saved["status"] == "failed"
    assert saved["prompt_version"] == "content-v1"
    assert saved["model"] == "configured-model"
