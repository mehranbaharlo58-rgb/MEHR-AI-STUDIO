"""Local desktop bridge runtime with fail-closed policy enforcement.

This module is platform-neutral. A Windows/macOS/Linux adapter must implement
DesktopAdapter and independently enforce OS permissions before local I/O.
It intentionally exposes no network listener and performs no OS input itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from threading import Event, RLock
from typing import Protocol

from .desktop_control import (
    ActionReplayGuard,
    ControlArbiter,
    DesktopAction,
    DesktopSessionPolicy,
    evaluate_action,
)


class DesktopAdapter(Protocol):
    """Narrow platform contract; implementations must not expose shell access."""

    def active_app_id(self) -> str | None:
        """Return a stable identifier for the currently focused application."""

    def display_size(self, display_id: str) -> tuple[int, int]:
        """Return current pixel dimensions for a known display."""

    def capture_screen(self, display_id: str) -> bytes:
        """Capture one user-authorized screenshot without persisting it."""

    def execute_action(self, action: DesktopAction, cancel_event: Event) -> None:
        """Execute one typed action and observe cancellation between steps."""


@dataclass(frozen=True)
class ScreenObservation:
    """One ephemeral screenshot and the app context observed with it."""

    session_id: str
    display_id: str
    active_app_id: str
    image_bytes: bytes


@dataclass(frozen=True)
class BridgeActionResult:
    """Machine-readable result; successful dispatch is not task success."""

    action_id: str
    accepted: bool
    reason: str
    requires_confirmation: bool = False


class DesktopBridgeRuntime:
    """Enforce session scope and human priority immediately before adapter I/O."""

    def __init__(
        self,
        *,
        policy: DesktopSessionPolicy,
        adapter: DesktopAdapter,
        arbiter: ControlArbiter | None = None,
        replay_guard: ActionReplayGuard | None = None,
    ) -> None:
        self._policy = policy
        self._adapter = adapter
        self._arbiter = arbiter or ControlArbiter()
        self._replay_guard = replay_guard or ActionReplayGuard()
        self._lock = RLock()
        self._cancel_event = Event()
        self._action_in_flight = False
        self._actions_executed = 0

    def observe(self, display_id: str = "primary") -> ScreenObservation:
        """Capture only when consent and the focused-app allowlist both pass."""
        with self._lock:
            if not self._policy.consent_granted:
                raise PermissionError("consent_missing")
            active_app_id = self._adapter.active_app_id()
            if active_app_id is None or active_app_id not in self._policy.allowed_app_ids:
                raise PermissionError("application_not_allowed")
            image_bytes = self._adapter.capture_screen(display_id)
            if not isinstance(image_bytes, bytes) or not image_bytes:
                raise RuntimeError("adapter_returned_empty_capture")
            return ScreenObservation(
                session_id=self._policy.session_id,
                display_id=display_id,
                active_app_id=active_app_id,
                image_bytes=image_bytes,
            )

    def execute(
        self,
        action: DesktopAction,
        *,
        explicitly_approved: bool = False,
    ) -> BridgeActionResult:
        """Validate, arbitrate, re-check focus and dispatch exactly one action."""
        with self._lock:
            if not self._replay_guard.accept_once(action.action_id):
                return BridgeActionResult(action.action_id, False, "duplicate_action")
            if self._action_in_flight:
                return BridgeActionResult(action.action_id, False, "another_action_in_flight")

        active_app_id = self._adapter.active_app_id()
        decision = evaluate_action(
            action,
            self._policy,
            active_app_id=active_app_id,
            explicitly_approved=explicitly_approved,
        )
        if not decision.allowed:
            return BridgeActionResult(
                action.action_id,
                False,
                decision.reason,
                decision.requires_confirmation,
            )

        if action.kind == "screenshot":
            return BridgeActionResult(action.action_id, False, "use_observe_api")

        width, height = self._adapter.display_size(action.display_id)
        action.validate_display_bounds(width, height)
        if self._adapter.active_app_id() != active_app_id:
            return BridgeActionResult(action.action_id, False, "active_application_changed")

        with self._lock:
            if self._actions_executed >= self._policy.max_actions:
                return BridgeActionResult(action.action_id, False, "session_action_limit")
            if not self._arbiter.acquire_agent():
                reason = "emergency_stopped" if self._arbiter.stopped else "human_has_control"
                return BridgeActionResult(action.action_id, False, reason)
            if self._cancel_event.is_set() or not self._arbiter.agent_may_act:
                return BridgeActionResult(action.action_id, False, "human_preempted")
            self._action_in_flight = True
            self._actions_executed += 1
            cancel_event = self._cancel_event

        try:
            # Do not hold the runtime lock during OS I/O: a physical-input hook
            # must be able to set cancellation while a drag or text action runs.
            self._adapter.execute_action(action, cancel_event)
            if cancel_event.is_set():
                return BridgeActionResult(action.action_id, False, "preempted_during_dispatch")
            return BridgeActionResult(action.action_id, True, "dispatched")
        finally:
            with self._lock:
                self._action_in_flight = False

    def on_human_input(self) -> None:
        """Preempt agent input when physical user input is detected."""
        with self._lock:
            self._cancel_event.set()
            self._arbiter.on_human_input()

    def yield_human_control(self) -> None:
        """Allow the agent to request control after the user yields it."""
        with self._lock:
            self._arbiter.yield_human_control()
            if not self._arbiter.stopped:
                self._cancel_event.clear()

    def emergency_stop(self) -> None:
        """Stop future agent actions for this session."""
        with self._lock:
            self._cancel_event.set()
            self._arbiter.emergency_stop()
