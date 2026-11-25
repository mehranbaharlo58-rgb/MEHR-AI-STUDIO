"""Tests for physical-input classification without a Windows desktop."""

import pytest

from mehr_ai_studio import windows_input_hook


def test_injected_keyboard_and_mouse_events_are_ignored():
    assert windows_input_hook.is_physical_input(
        windows_input_hook.LLKHF_INJECTED, windows_input_hook.LLKHF_INJECTED,
        windows_input_hook.LLKHF_LOWER_IL_INJECTED,
    ) is False
    assert windows_input_hook.is_physical_input(
        windows_input_hook.LLMHF_INJECTED, windows_input_hook.LLMHF_INJECTED,
        windows_input_hook.LLMHF_LOWER_IL_INJECTED,
    ) is False


def test_lower_integrity_injected_events_are_ignored():
    assert windows_input_hook.is_physical_input(
        windows_input_hook.LLKHF_LOWER_IL_INJECTED,
        windows_input_hook.LLKHF_INJECTED,
        windows_input_hook.LLKHF_LOWER_IL_INJECTED,
    ) is False


def test_uninjected_physical_events_are_detected():
    assert windows_input_hook.is_physical_input(0, 0x10, 0x02) is True


def test_hook_refuses_non_windows_platform(monkeypatch):
    monkeypatch.setattr(windows_input_hook.sys, "platform", "linux")
    with pytest.raises(RuntimeError, match="requires_windows"):
        windows_input_hook.WindowsPhysicalInputHook(lambda: None)
