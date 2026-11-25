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


def test_hook_lifecycle_and_callback_ignore_injected_events(monkeypatch):
    import ctypes
    import threading

    class FakeFunction:
        def __init__(self, callback):
            self.callback = callback
            self.argtypes = None
            self.restype = None

        def __call__(self, *args):
            return self.callback(*args)

    class FakeUser32:
        def __init__(self):
            self.condition = threading.Condition()
            self.messages = []
            self.unhooked = []
            self.next_handle = 10
            self.SetWindowsHookExW = FakeFunction(self.install)
            self.CallNextHookEx = FakeFunction(lambda *args: 0)
            self.UnhookWindowsHookEx = FakeFunction(self.unhook)
            self.GetMessageW = FakeFunction(self.get_message)
            self.PeekMessageW = FakeFunction(lambda *args: 0)
            self.PostThreadMessageW = FakeFunction(self.post_message)
            self.TranslateMessage = FakeFunction(lambda *args: 1)
            self.DispatchMessageW = FakeFunction(lambda *args: 1)

        def install(self, *args):
            self.next_handle += 1
            return self.next_handle

        def unhook(self, handle):
            self.unhooked.append(handle)
            return 1

        def get_message(self, *args):
            with self.condition:
                while not self.messages:
                    self.condition.wait(timeout=2)
                message = self.messages.pop(0)
            return 0 if message == windows_input_hook.WM_QUIT else 1

        def post_message(self, thread_id, message, *args):
            with self.condition:
                self.messages.append(message)
                self.condition.notify_all()
            return 1

    class FakeKernel32:
        GetCurrentThreadId = FakeFunction(lambda: 123)
        GetModuleHandleW = FakeFunction(lambda _name: 1)

    user32 = FakeUser32()
    kernel32 = FakeKernel32()

    def fake_windll(name, **_kwargs):
        return user32 if name == "user32" else kernel32

    monkeypatch.setattr(windows_input_hook.ctypes, "WinDLL", fake_windll, raising=False)
    monkeypatch.setattr(
        windows_input_hook.ctypes, "WINFUNCTYPE",
        windows_input_hook.ctypes.CFUNCTYPE, raising=False
    )
    monkeypatch.setattr(windows_input_hook.sys, "platform", "win32")
    notifications = []
    hook = windows_input_hook.WindowsPhysicalInputHook(
        lambda: notifications.append("physical")
    )
    hook.start()
    assert hook.running is True

    keyboard_event = windows_input_hook._KBDLLHOOKSTRUCT()
    keyboard_event.flags = 0
    keyboard_callback = hook._callbacks[0]
    keyboard_callback(
        0, windows_input_hook.WM_KEYDOWN, ctypes.addressof(keyboard_event)
    )
    assert notifications == ["physical"]

    keyboard_event.flags = windows_input_hook.LLKHF_INJECTED
    keyboard_callback(
        0, windows_input_hook.WM_KEYDOWN, ctypes.addressof(keyboard_event)
    )
    assert notifications == ["physical"]

    hook.stop()
    assert hook.running is False
    assert len(user32.unhooked) == 2
