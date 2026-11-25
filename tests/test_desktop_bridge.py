"""Tests for the platform-neutral desktop bridge runtime."""

import pytest

from mehr_ai_studio.desktop_bridge import DesktopBridgeRuntime
from mehr_ai_studio.desktop_control import DesktopAction, DesktopSessionPolicy


class FakeAdapter:
    def __init__(self):
        self.app_id = "com.example.editor"
        self.actions = []
        self.capture_count = 0
        self.change_focus_during_size = False

    def active_app_id(self):
        return self.app_id

    def display_size(self, display_id):
        if self.change_focus_during_size:
            self.app_id = "com.example.other"
        return (1920, 1080)

    def capture_screen(self, display_id):
        self.capture_count += 1
        return b"ephemeral-image"

    def execute_action(self, action):
        self.actions.append(action)


def make_policy(**changes):
    values = {
        "session_id": "session-0001",
        "consent_granted": True,
        "mode": "copilot",
        "allowed_app_ids": ["com.example.editor"],
        "allow_pointer_control": True,
        "allow_keyboard_control": True,
    }
    values.update(changes)
    return DesktopSessionPolicy(**values)


def make_action(kind="click", **changes):
    values = {
        "action_id": "action-0001",
        "session_id": "session-0001",
        "kind": kind,
        "x": 100,
        "y": 200,
    }
    if kind == "type_text":
        values.pop("x")
        values.pop("y")
        values["text"] = "hello"
    values.update(changes)
    return DesktopAction(**values)


def test_observe_requires_consent_and_allowed_foreground_app():
    adapter = FakeAdapter()
    runtime = DesktopBridgeRuntime(
        policy=make_policy(consent_granted=False), adapter=adapter
    )
    with pytest.raises(PermissionError, match="consent_missing"):
        runtime.observe()
    assert adapter.capture_count == 0

    runtime = DesktopBridgeRuntime(
        policy=make_policy(), adapter=adapter
    )
    observation = runtime.observe()
    assert observation.image_bytes == b"ephemeral-image"
    assert observation.active_app_id == "com.example.editor"


def test_observe_rejects_unapproved_foreground_app():
    adapter = FakeAdapter()
    adapter.app_id = "com.example.other"
    runtime = DesktopBridgeRuntime(policy=make_policy(), adapter=adapter)
    with pytest.raises(PermissionError, match="application_not_allowed"):
        runtime.observe()
    assert adapter.capture_count == 0


def test_execute_requires_explicit_approval_and_human_yield():
    adapter = FakeAdapter()
    runtime = DesktopBridgeRuntime(policy=make_policy(), adapter=adapter)
    denied = runtime.execute(make_action())
    assert denied.requires_confirmation is True
    assert adapter.actions == []

    runtime.yield_human_control()
    approved = runtime.execute(
        make_action(action_id="action-0002"), explicitly_approved=True
    )
    assert approved.accepted is True
    assert len(adapter.actions) == 1


def test_execute_rejects_duplicate_action_id():
    adapter = FakeAdapter()
    runtime = DesktopBridgeRuntime(policy=make_policy(), adapter=adapter)
    runtime.yield_human_control()
    item = make_action()
    first = runtime.execute(item, explicitly_approved=True)
    second = runtime.execute(item, explicitly_approved=True)
    assert first.accepted is True
    assert second.reason == "duplicate_action"
    assert len(adapter.actions) == 1


def test_human_input_preempts_agent_and_emergency_stop_is_sticky():
    adapter = FakeAdapter()
    runtime = DesktopBridgeRuntime(policy=make_policy(), adapter=adapter)
    runtime.yield_human_control()
    runtime.on_human_input()
    result = runtime.execute(
        make_action(), explicitly_approved=True
    )
    assert result.reason == "human_has_control"
    assert adapter.actions == []

    runtime.yield_human_control()
    runtime.emergency_stop()
    result = runtime.execute(
        make_action(action_id="action-0002"), explicitly_approved=True
    )
    assert result.reason == "human_has_control"
    assert adapter.actions == []


def test_execute_rechecks_foreground_application_before_input():
    adapter = FakeAdapter()
    adapter.change_focus_during_size = True
    runtime = DesktopBridgeRuntime(policy=make_policy(), adapter=adapter)
    runtime.yield_human_control()
    result = runtime.execute(make_action(), explicitly_approved=True)
    assert result.reason == "active_application_changed"
    assert adapter.actions == []


def test_execute_rejects_out_of_bounds_coordinates():
    adapter = FakeAdapter()
    runtime = DesktopBridgeRuntime(policy=make_policy(), adapter=adapter)
    runtime.yield_human_control()
    with pytest.raises(ValueError, match="outside"):
        runtime.execute(
            make_action(x=3000), explicitly_approved=True
        )
    assert adapter.actions == []
