"""Windows low-level physical-input monitor for human-priority arbitration.

The hook is opt-in and must run only during an explicitly consented session.
Injected events are ignored so PyAutoGUI/SendInput agent events do not preempt
the agent itself. This module never captures key contents or mouse coordinates.
"""

from __future__ import annotations

import ctypes
import sys
import threading
from ctypes import wintypes
from collections.abc import Callable


WH_KEYBOARD_LL = 13
WH_MOUSE_LL = 14
WM_QUIT = 0x0012
WM_KEYDOWN = 0x0100
WM_SYSKEYDOWN = 0x0104
WM_MOUSEMOVE = 0x0200
WM_LBUTTONDOWN = 0x0201
WM_RBUTTONDOWN = 0x0204
WM_MBUTTONDOWN = 0x0207
WM_XBUTTONDOWN = 0x020B
LLKHF_INJECTED = 0x10
LLKHF_LOWER_IL_INJECTED = 0x02
LLMHF_INJECTED = 0x01
LLMHF_LOWER_IL_INJECTED = 0x02


def is_physical_input(flags: int, injected_mask: int, lower_il_mask: int) -> bool:
    """Return false for OS-tagged injected input; do not inspect event payloads."""
    return not bool(flags & (injected_mask | lower_il_mask))


class _KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", wintypes.DWORD),
        ("scanCode", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class _MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("pt", wintypes.POINT),
        ("mouseData", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class WindowsPhysicalInputHook:
    """Global low-level hooks that notify on physical input without recording it."""

    def __init__(self, on_input: Callable[[], None]) -> None:
        if sys.platform != "win32":
            raise RuntimeError("windows_input_hook_requires_windows")
        self._on_input = on_input
        self._thread: threading.Thread | None = None
        self._thread_id: int | None = None
        self._ready = threading.Event()
        self._stopped = threading.Event()
        self._error: str | None = None
        self._keyboard_hook = None
        self._mouse_hook = None
        self._callbacks: tuple[object, object] | None = None

    @property
    def running(self) -> bool:
        return self._thread is not None and self._ready.is_set() and not self._stopped.is_set()

    def start(self, timeout: float = 5.0) -> None:
        """Start hooks and fail closed if Windows cannot install both hooks."""
        if self._thread is not None:
            raise RuntimeError("input_hook_already_started")
        if not 0.1 <= timeout <= 30:
            raise ValueError("invalid_hook_start_timeout")
        self._thread = threading.Thread(
            target=self._message_loop, name="mehr-human-input-hook", daemon=True
        )
        self._thread.start()
        if not self._ready.wait(timeout):
            self.stop()
            raise RuntimeError("input_hook_start_timeout")
        if self._error:
            self.stop()
            raise RuntimeError(self._error)

    def stop(self, timeout: float = 5.0) -> None:
        """Uninstall hooks by stopping their owning message-loop thread."""
        if self._thread is None:
            return
        if self._thread_id is not None:
            user32 = ctypes.WinDLL("user32", use_last_error=True)
            user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
        self._thread.join(timeout)
        if self._thread.is_alive():
            raise RuntimeError("input_hook_stop_timeout")
        self._thread = None
        self._thread_id = None

    def _notify(self) -> None:
        try:
            self._on_input()
        except (RuntimeError, OSError, ValueError):
            # Never allow expected callback failures to break the OS hook.
            return

    def _message_loop(self) -> None:
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        hook_proc_type = ctypes.WINFUNCTYPE(
            ctypes.c_ssize_t, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM
        )
        user32.SetWindowsHookExW.restype = wintypes.HHOOK
        user32.SetWindowsHookExW.argtypes = [
            ctypes.c_int, hook_proc_type, wintypes.HINSTANCE, wintypes.DWORD
        ]
        user32.CallNextHookEx.restype = ctypes.c_ssize_t
        user32.CallNextHookEx.argtypes = [
            wintypes.HHOOK, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM
        ]
        user32.UnhookWindowsHookEx.argtypes = [wintypes.HHOOK]
        user32.GetMessageW.argtypes = [
            ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT
        ]
        kernel32.GetModuleHandleW.restype = wintypes.HMODULE
        self._thread_id = kernel32.GetCurrentThreadId()
        module = kernel32.GetModuleHandleW(None)

        def keyboard_proc(code, message, data):
            if code >= 0 and message in (WM_KEYDOWN, WM_SYSKEYDOWN):
                event = ctypes.cast(data, ctypes.POINTER(_KBDLLHOOKSTRUCT)).contents
                if is_physical_input(
                    event.flags, LLKHF_INJECTED, LLKHF_LOWER_IL_INJECTED
                ):
                    self._notify()
            return user32.CallNextHookEx(
                self._keyboard_hook, code, message, data
            )

        def mouse_proc(code, message, data):
            if code >= 0 and message in (
                WM_MOUSEMOVE, WM_LBUTTONDOWN, WM_RBUTTONDOWN,
                WM_MBUTTONDOWN, WM_XBUTTONDOWN,
            ):
                event = ctypes.cast(data, ctypes.POINTER(_MSLLHOOKSTRUCT)).contents
                if is_physical_input(
                    event.flags, LLMHF_INJECTED, LLMHF_LOWER_IL_INJECTED
                ):
                    self._notify()
            return user32.CallNextHookEx(self._mouse_hook, code, message, data)

        keyboard_callback = hook_proc_type(keyboard_proc)
        mouse_callback = hook_proc_type(mouse_proc)
        self._callbacks = (keyboard_callback, mouse_callback)
        try:
            self._keyboard_hook = user32.SetWindowsHookExW(
                WH_KEYBOARD_LL, keyboard_callback, module, 0
            )
            if not self._keyboard_hook:
                raise OSError(ctypes.get_last_error(), "keyboard_hook_install_failed")
            self._mouse_hook = user32.SetWindowsHookExW(
                WH_MOUSE_LL, mouse_callback, module, 0
            )
            if not self._mouse_hook:
                raise OSError(ctypes.get_last_error(), "mouse_hook_install_failed")
            self._ready.set()
            message = wintypes.MSG()
            while True:
                result = user32.GetMessageW(ctypes.byref(message), None, 0, 0)
                if result <= 0:
                    break
                user32.TranslateMessage(ctypes.byref(message))
                user32.DispatchMessageW(ctypes.byref(message))
        except (OSError, RuntimeError, ValueError, TypeError) as exc:
            self._error = f"input_hook_install_or_loop_failed:{type(exc).__name__}"
            self._ready.set()
        finally:
            if self._mouse_hook:
                user32.UnhookWindowsHookEx(self._mouse_hook)
                self._mouse_hook = None
            if self._keyboard_hook:
                user32.UnhookWindowsHookEx(self._keyboard_hook)
                self._keyboard_hook = None
            self._stopped.set()
