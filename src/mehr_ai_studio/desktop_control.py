"""Policy and protocol primitives for the MEHR desktop-control bridge.

This module deliberately does not inject operating-system input. It validates
requests and models consent, approvals, replay protection, and human priority.
A platform bridge must enforce these decisions again immediately before I/O.
"""

# isort: off
from __future__ import annotations

from collections import deque
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
# isort: on


ActionKind = Literal[
    "screenshot",
    "move",
    "click",
    "double_click",
    "context_click",
    "scroll",
    "keypress",
    "type_text",
    "drag",
]


class DesktopAction(BaseModel):
    """A bounded, typed request; never an arbitrary shell or script command."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    action_id: str = Field(min_length=8, max_length=100, pattern=r"^[A-Za-z0-9._:-]+$")
    session_id: str = Field(min_length=8, max_length=100, pattern=r"^[A-Za-z0-9._:-]+$")
    kind: ActionKind
    display_id: str = Field(default="primary", min_length=1, max_length=80)
    x: int | None = Field(default=None, ge=0, le=32767)
    y: int | None = Field(default=None, ge=0, le=32767)
    end_x: int | None = Field(default=None, ge=0, le=32767)
    end_y: int | None = Field(default=None, ge=0, le=32767)
    button: Literal["left", "right", "middle"] = "left"
    scroll_delta: int | None = Field(default=None, ge=-2400, le=2400)
    keys: list[str] = Field(default_factory=list, max_length=4)
    text: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def validate_shape(self) -> DesktopAction:
        pointer_kinds = {"move", "click", "double_click", "context_click", "scroll"}
        if self.kind in pointer_kinds and (self.x is None or self.y is None):
            raise ValueError("pointer actions require x and y")
        if self.kind == "drag" and any(
            value is None for value in (self.x, self.y, self.end_x, self.end_y)
        ):
            raise ValueError("drag requires start and end coordinates")
        if self.kind == "scroll" and self.scroll_delta is None:
            raise ValueError("scroll requires scroll_delta")
        if self.kind == "keypress" and not self.keys:
            raise ValueError("keypress requires at least one key")
        if self.kind != "keypress" and self.keys:
            raise ValueError("keys are only valid for keypress")
        if self.kind == "type_text" and not self.text:
            raise ValueError("type_text requires non-empty text")
        if self.kind != "type_text" and self.text is not None:
            raise ValueError("text is only valid for type_text")
        return self

    def validate_display_bounds(self, width: int, height: int) -> None:
        """Reject coordinates outside the current, trusted display dimensions."""
        if not 1 <= width <= 32768 or not 1 <= height <= 32768:
            raise ValueError("invalid display dimensions")
        for coordinate, maximum, label in (
            (self.x, width, "x"),
            (self.end_x, width, "end_x"),
            (self.y, height, "y"),
            (self.end_y, height, "end_y"),
        ):
            if coordinate is not None and coordinate >= maximum:
                raise ValueError(f"{label} is outside the current display")


class DesktopSessionPolicy(BaseModel):
    """User-approved scope for one paired desktop session."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    session_id: str = Field(min_length=8, max_length=100)
    consent_granted: bool = False
    mode: Literal["observe", "guide", "copilot", "delegated"] = "observe"
    allowed_app_ids: list[str] = Field(default_factory=list, max_length=30)
    allow_pointer_control: bool = False
    allow_keyboard_control: bool = False
    max_actions: int = Field(default=20, ge=1, le=200)


class ActionDecision(BaseModel):
    allowed: bool
    requires_confirmation: bool
    reason: str


def evaluate_action(
    action: DesktopAction,
    policy: DesktopSessionPolicy,
    *,
    active_app_id: str | None,
    explicitly_approved: bool = False,
) -> ActionDecision:
    """Fail-closed policy decision. The bridge must call this before every I/O."""
    if action.session_id != policy.session_id:
        return ActionDecision(
            allowed=False, requires_confirmation=False, reason="session_mismatch"
        )
    if not policy.consent_granted:
        return ActionDecision(
            allowed=False, requires_confirmation=False, reason="consent_missing"
        )
    if active_app_id is None or active_app_id not in policy.allowed_app_ids:
        return ActionDecision(
            allowed=False, requires_confirmation=False, reason="application_not_allowed"
        )
    if action.kind == "screenshot":
        return ActionDecision(allowed=True, requires_confirmation=False, reason="observe")
    if policy.mode == "observe":
        return ActionDecision(
            allowed=False, requires_confirmation=False, reason="observe_only"
        )
    if action.kind == "move":
        if policy.mode not in {"guide", "copilot", "delegated"}:
            return ActionDecision(
                allowed=False, requires_confirmation=False, reason="mode_disallows_pointer"
            )
        if not policy.allow_pointer_control:
            return ActionDecision(
                allowed=False, requires_confirmation=False, reason="pointer_control_disabled"
            )
        return ActionDecision(
            allowed=True, requires_confirmation=False, reason="visual_pointer_allowed"
        )
    if policy.mode == "guide":
        return ActionDecision(
            allowed=False, requires_confirmation=False, reason="guide_mode_no_input"
        )
    if (
        action.kind in {"click", "double_click", "context_click", "scroll", "drag"}
        and not policy.allow_pointer_control
    ):
        return ActionDecision(
            allowed=False, requires_confirmation=False, reason="pointer_control_disabled"
        )
    if action.kind in {"keypress", "type_text"} and not policy.allow_keyboard_control:
        return ActionDecision(
            allowed=False, requires_confirmation=False, reason="keyboard_control_disabled"
        )
    if not explicitly_approved:
        return ActionDecision(
            allowed=False, requires_confirmation=True, reason="just_in_time_approval_required"
        )
    return ActionDecision(
        allowed=True, requires_confirmation=False, reason="approved_for_this_action"
    )


class ActionReplayGuard:
    """Bounded in-memory replay guard; persist/coordinate it for distributed workers."""

    def __init__(self, capacity: int = 2000) -> None:
        if not 1 <= capacity <= 100_000:
            raise ValueError("capacity must be between 1 and 100000")
        self._seen: set[str] = set()
        self._order: deque[str] = deque()
        self._capacity = capacity

    def accept_once(self, action_id: str) -> bool:
        if not action_id or action_id in self._seen:
            return False
        self._seen.add(action_id)
        self._order.append(action_id)
        if len(self._order) > self._capacity:
            expired = self._order.popleft()
            self._seen.discard(expired)
        return True


class ControlArbiter:
    """Ensures human input preempts agent input in the local bridge process."""

    def __init__(self) -> None:
        self._human_has_control = False
        self._agent_has_control = False
        self._stopped = False

    def acquire_agent(self) -> bool:
        if self._stopped or self._human_has_control:
            return False
        self._agent_has_control = True
        return True

    def on_human_input(self) -> None:
        self._human_has_control = True
        self._agent_has_control = False

    def yield_human_control(self) -> None:
        self._human_has_control = False

    def emergency_stop(self) -> None:
        self._stopped = True
        self._agent_has_control = False

    def reset_after_new_consent(self) -> None:
        self._stopped = False
        self._human_has_control = True
        self._agent_has_control = False

    @property
    def stopped(self) -> bool:
        return self._stopped

    @property
    def agent_may_act(self) -> bool:
        return (
            not self._stopped
            and not self._human_has_control
            and self._agent_has_control
        )
