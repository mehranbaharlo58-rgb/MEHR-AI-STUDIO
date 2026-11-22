"""Tests for strict workflow data contracts."""

import pytest
from pydantic import ValidationError

from mehr_ai_studio.contracts import (
    ContentBriefContract,
    GeneratedAssetContract,
    ProviderResultContract,
    QualityReportContract,
    WorkflowRunContract,
)


def test_content_brief_contract_normalizes_whitespace():
    brief = ContentBriefContract(
        goal="  Explain the service  ",
        audience=" small businesses ",
        channel=" website ",
    )
    assert brief.goal == "Explain the service"
    assert brief.language == "Persian"
    assert brief.key_points == []


@pytest.mark.parametrize("payload", [
    {"goal": "", "audience": "users", "channel": "web"},
    {"goal": "goal", "audience": "users", "channel": "web", "unexpected": True},
    {"goal": "goal", "audience": "users", "channel": "web", "key_points": ["ok", " "]},
])
def test_content_brief_rejects_invalid_contract(payload):
    with pytest.raises(ValidationError):
        ContentBriefContract.model_validate(payload)


def test_generated_asset_and_provider_result_require_content():
    with pytest.raises(ValidationError):
        GeneratedAssetContract(content=" ")
    with pytest.raises(ValidationError):
        ProviderResultContract(text="", model="test")


@pytest.mark.parametrize("score", [-1, 101])
def test_quality_report_rejects_out_of_range_score(score):
    with pytest.raises(ValidationError):
        QualityReportContract(score=score, checks={})


def test_workflow_run_requires_valid_status_and_tenant():
    base = {
        "run_id": "run-1",
        "tenant_id": "tenant-a",
        "status": "queued",
        "created_at": "2026-11-22T00:00:00Z",
        "updated_at": "2026-11-22T00:00:00Z",
    }
    assert WorkflowRunContract.model_validate(base).attempt == 1
    with pytest.raises(ValidationError):
        WorkflowRunContract.model_validate({**base, "status": "done"})
    with pytest.raises(ValidationError):
        WorkflowRunContract.model_validate({**base, "tenant_id": ""})
