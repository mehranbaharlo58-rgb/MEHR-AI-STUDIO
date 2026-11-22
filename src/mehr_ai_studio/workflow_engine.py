"""Typed workflow stage registry and lifecycle transition rules.

The content workflow executes through registered stages. Lifecycle transitions
are also enforced by the persistence layer before workflow snapshots are updated.
"""
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Generic, TypeVar

from pydantic import BaseModel

InputT = TypeVar("InputT", bound=BaseModel)
OutputT = TypeVar("OutputT", bound=BaseModel)


class WorkflowStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    FAILED = "failed"
    SUCCEEDED = "succeeded"
    CANCELLED = "cancelled"


_ALLOWED_TRANSITIONS: dict[WorkflowStatus, frozenset[WorkflowStatus]] = {
    WorkflowStatus.QUEUED: frozenset(
        {WorkflowStatus.RUNNING, WorkflowStatus.CANCELLED}
    ),
    WorkflowStatus.RUNNING: frozenset(
        {
            WorkflowStatus.WAITING_APPROVAL,
            WorkflowStatus.FAILED,
            WorkflowStatus.SUCCEEDED,
            WorkflowStatus.CANCELLED,
        }
    ),
    WorkflowStatus.WAITING_APPROVAL: frozenset(
        {WorkflowStatus.RUNNING, WorkflowStatus.CANCELLED}
    ),
    WorkflowStatus.FAILED: frozenset(
        {WorkflowStatus.RUNNING, WorkflowStatus.CANCELLED}
    ),
    WorkflowStatus.SUCCEEDED: frozenset(),
    WorkflowStatus.CANCELLED: frozenset(),
}


def transition_status(
    current: WorkflowStatus | str, target: WorkflowStatus | str
) -> WorkflowStatus:
    """Validate and return a legal workflow lifecycle transition."""
    current_status = WorkflowStatus(current)
    target_status = WorkflowStatus(target)
    if target_status == current_status:
        return target_status
    if target_status not in _ALLOWED_TRANSITIONS[current_status]:
        raise ValueError(
            f"invalid workflow transition: {current_status.value} -> {target_status.value}"
        )
    return target_status


@dataclass(frozen=True)
class StageDefinition(Generic[InputT, OutputT]):
    """One typed, synchronous workflow stage."""

    name: str
    input_model: type[InputT]
    output_model: type[OutputT]
    handler: Callable[[InputT], OutputT | dict[str, Any]]

    def execute(self, payload: InputT | dict[str, Any]) -> OutputT:
        validated_input = self.input_model.model_validate(payload)
        raw_output = self.handler(validated_input)
        return self.output_model.model_validate(raw_output)


class StageRegistry:
    """Insertion-ordered registry with unique, stable stage identifiers."""

    def __init__(self) -> None:
        self._stages: dict[str, StageDefinition[Any, Any]] = {}

    def register(
        self, stage: StageDefinition[InputT, OutputT]
    ) -> StageDefinition[InputT, OutputT]:
        if not isinstance(stage, StageDefinition):
            raise TypeError("stage must be a StageDefinition")
        name = stage.name.strip() if isinstance(stage.name, str) else ""
        if not name:
            raise ValueError("stage name is required")
        if name != stage.name:
            raise ValueError("stage name must not contain surrounding whitespace")
        if name in self._stages:
            raise ValueError(f"stage already registered: {name}")
        if not issubclass(stage.input_model, BaseModel):
            raise TypeError("input_model must be a Pydantic model")
        if not issubclass(stage.output_model, BaseModel):
            raise TypeError("output_model must be a Pydantic model")
        if not callable(stage.handler):
            raise TypeError("stage handler must be callable")
        self._stages[name] = stage
        return stage

    def get(self, name: str) -> StageDefinition[Any, Any]:
        try:
            return self._stages[name]
        except KeyError as exc:
            raise KeyError(f"unknown workflow stage: {name}") from exc

    def ordered(self) -> tuple[StageDefinition[Any, Any], ...]:
        """Return a stable snapshot in registration order."""
        return tuple(self._stages.values())

    def __len__(self) -> int:
        return len(self._stages)
