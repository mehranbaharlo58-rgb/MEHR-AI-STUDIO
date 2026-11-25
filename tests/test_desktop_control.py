"""Tests for MEHR desktop action policy and human-control arbitration."""
import pytest
from pydantic import ValidationError

from mehr_ai_studio.desktop_control import (
    ActionReplayGuard,
    ControlArbiter,
    DesktopAction,
    DesktopSessionPolicy,
    evaluate_action,
)


def action(kind="click", **changes):
    values = {
        "action_id": "action-0001",
        "session_id": "session-0001",
        "kind": kind,
        "x": 10,
        "y": 20,
    }
    if kind not in {"click", "move", "double_click", "context_click", "scroll"}:
        values.pop("x", None)
        values.pop("y", None)
    values.update(changes)
    return DesktopAction(**values)


def policy(**changes):
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


def test_action_rejects_unknown_fields_and_incomplete_pointer_request():
    with pytest.raises(ValidationError):
        DesktopAction(
            action_id="action-0001",
            session_id="session-0001",
            kind="click",
            x=10,
            y=20,
            shell_command="rm -rf",
        )
    with pytest.raises(ValidationError):
        DesktopAction(
            action_id="action-0001",
            session_id="session-0001",
            kind="click",
        )


def test_action_validates_current_display_bounds():
    item = action()
    item.validate_display_bounds(100, 100)
    with pytest.raises(ValueError, match="outside"):
        item.validate_display_bounds(10, 100)


def test_observe_mode_allows_only_screenshot():
    snapshot = action("screenshot")
    result = evaluate_action(
        snapshot, policy(mode="observe"), active_app_id="com.example.editor"
    )
    assert result.allowed is True
    assert result.requires_confirmation is False

    click = action()
    result = evaluate_action(
        click, policy(mode="observe"), active_app_id="com.example.editor"
    )
    assert result.allowed is False
    assert result.reason == "observe_only"


def test_missing_consent_or_unapproved_application_fails_closed():
    item = action()
    assert evaluate_action(
        item, policy(consent_granted=False), active_app_id="com.example.editor"
    ).reason == "consent_missing"
    assert evaluate_action(
        item, policy(), active_app_id="com.example.other"
    ).reason == "application_not_allowed"


def test_pointer_move_can_be_used_in_guide_mode_but_not_click():
    move = action("move")
    decision = evaluate_action(
        move, policy(mode="guide"), active_app_id="com.example.editor"
    )
    assert decision.allowed is True

    click = action()
    decision = evaluate_action(
        click, policy(mode="guide"), active_app_id="com.example.editor"
    )
    assert decision.allowed is False


def test_copilot_input_requires_action_specific_approval():
    click = action()
    decision = evaluate_action(
        click, policy(), active_app_id="com.example.editor"
    )
    assert decision.allowed is False
    assert decision.requires_confirmation is True

    approved = evaluate_action(
        click,
        policy(),
        active_app_id="com.example.editor",
        explicitly_approved=True,
    )
    assert approved.allowed is True


def test_keyboard_requires_explicit_scope_and_approval():
    item = action(
        "type_text",
        text="hello",
    )
    no_scope = evaluate_action(
        item,
        policy(allow_keyboard_control=False),
        active_app_id="com.example.editor",
        explicitly_approved=True,
    )
    assert no_scope.allowed is False
    assert no_scope.reason == "keyboard_control_disabled"

    requires_approval = evaluate_action(
        item, policy(), active_app_id="com.example.editor"
    )
    assert requires_approval.requires_confirmation is True


def test_action_replay_guard_rejects_duplicate_ids_and_bounds_memory():
    guard = ActionReplayGuard(capacity=2)
    assert guard.accept_once("a1") is True
    assert guard.accept_once("a1") is False
    assert guard.accept_once("a2") is True
    assert guard.accept_once("a3") is True
    # The oldest ID is evicted from this bounded in-memory replay window.
    assert guard.accept_once("a1") is True


def test_human_input_preempts_agent_and_emergency_stop_is_sticky():
    arbiter = ControlArbiter()
    arbiter.yield_human_control()
    assert arbiter.acquire_agent() is True
    assert arbiter.agent_may_act is True

    arbiter.on_human_input()
    assert arbiter.agent_may_act is False
    assert arbiter.acquire_agent() is False

    arbiter.yield_human_control()
    assert arbiter.acquire_agent() is True
    arbiter.emergency_stop()
    assert arbiter.agent_may_act is False
    assert arbiter.acquire_agent() is False

    arbiter.reset_after_new_consent()
    assert arbiter.acquire_agent() is False
