import pytest
from pydantic import BaseModel, Field, ValidationError

from mehr_ai_studio.workflow_engine import (
    StageDefinition,
    StageRegistry,
    WorkflowStatus,
    transition_status,
)


class BriefInput(BaseModel):
    topic: str = Field(min_length=1)


class PromptOutput(BaseModel):
    prompt: str


class InvalidOutput(BaseModel):
    prompt: str


def test_registered_stage_validates_typed_input_and_output():
    stage = StageDefinition(
        name="build_prompt",
        input_model=BriefInput,
        output_model=PromptOutput,
        handler=lambda brief: {"prompt": f"Write about {brief.topic}"},
    )

    result = stage.execute({"topic": "engineering"})

    assert isinstance(result, PromptOutput)
    assert result.prompt == "Write about engineering"


def test_stage_rejects_invalid_input_and_output():
    stage = StageDefinition(
        name="build_prompt",
        input_model=BriefInput,
        output_model=PromptOutput,
        handler=lambda brief: {"unexpected": brief.topic},
    )

    with pytest.raises(ValidationError):
        stage.execute({"topic": ""})

    with pytest.raises(ValidationError):
        stage.execute({"topic": "engineering"})


def test_registry_preserves_order_and_rejects_duplicate_names():
    registry = StageRegistry()
    first = StageDefinition(
        "brief",
        BriefInput,
        PromptOutput,
        lambda value: {"prompt": value.topic},
    )
    second = StageDefinition(
        "generation",
        BriefInput,
        PromptOutput,
        lambda value: {"prompt": value.topic},
    )

    registry.register(first)
    registry.register(second)

    assert [stage.name for stage in registry.ordered()] == ["brief", "generation"]
    assert registry.get("brief") is first
    assert len(registry) == 2
    with pytest.raises(ValueError, match="already registered"):
        registry.register(first)


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (WorkflowStatus.QUEUED, WorkflowStatus.RUNNING),
        (WorkflowStatus.RUNNING, WorkflowStatus.WAITING_APPROVAL),
        (WorkflowStatus.WAITING_APPROVAL, WorkflowStatus.RUNNING),
        (WorkflowStatus.RUNNING, WorkflowStatus.FAILED),
        (WorkflowStatus.FAILED, WorkflowStatus.RUNNING),
        (WorkflowStatus.RUNNING, WorkflowStatus.SUCCEEDED),
        (WorkflowStatus.QUEUED, WorkflowStatus.CANCELLED),
        (WorkflowStatus.RUNNING, WorkflowStatus.CANCELLED),
    ],
)
def test_allowed_workflow_transitions(current, target):
    assert transition_status(current, target) is target


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (WorkflowStatus.QUEUED, WorkflowStatus.SUCCEEDED),
        (WorkflowStatus.SUCCEEDED, WorkflowStatus.RUNNING),
        (WorkflowStatus.CANCELLED, WorkflowStatus.RUNNING),
        (WorkflowStatus.FAILED, WorkflowStatus.SUCCEEDED),
        (WorkflowStatus.WAITING_APPROVAL, WorkflowStatus.SUCCEEDED),
    ],
)
def test_invalid_workflow_transitions_are_rejected(current, target):
    with pytest.raises(ValueError, match="invalid workflow transition"):
        transition_status(current, target)


def test_unknown_workflow_status_is_rejected():
    with pytest.raises(ValueError):
        transition_status("unknown", WorkflowStatus.RUNNING)
