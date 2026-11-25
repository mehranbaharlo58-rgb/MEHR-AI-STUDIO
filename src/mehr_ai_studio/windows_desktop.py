"""Windows desktop adapter using explicit, typed UI operations only.

Install the optional dependencies with:
    pip install "mehr-ai-studio[desktop-windows]"

The adapter does not open a listener, launch processes, or execute shell commands.
The caller must enforce consent, application allowlists, approvals, and arbitration
through DesktopBridgeRuntime before invoking this adapter.
"""

from __future__ import annotations

import io
import sys
from pathlib import Path
from threading import RLock

from .desktop_control import DesktopAction


class WindowsDesktopAdapter:
    """Capture a selected monitor and dispatch bounded mouse/keyboard actions."""

    def __init__(self) -> None:
        if sys.platform != "win32":
            raise RuntimeError("windows_desktop_adapter_requires_windows")

        try:
            import mss
            import psutil
            import pyautogui
            import win32gui
            import win32process
            from PIL import Image
        except ImportError as exc:
            raise RuntimeError(
                "install_optional_dependencies: pip install mehr-ai-studio[desktop-windows]"
            ) from exc

        self._mss = mss
        self._psutil = psutil
        self._pyautogui = pyautogui
        self._win32gui = win32gui
        self._win32process = win32process
        self._image = Image
        self._lock = RLock()

        # PyAutoGUI's corner fail-safe remains enabled as a local emergency path.
        self._pyautogui.FAILSAFE = True
        self._pyautogui.PAUSE = 0.03

    def active_app_id(self) -> str | None:
        """Return the foreground process executable stem as a stable app ID."""
        with self._lock:
            hwnd = self._win32gui.GetForegroundWindow()
            if not hwnd:
                return None
            _, process_id = self._win32process.GetWindowThreadProcessId(hwnd)
            if not process_id:
                return None
            try:
                executable = self._psutil.Process(process_id).name()
            except (self._psutil.Error, OSError):
                return None
            return Path(executable).stem.casefold() or None

    @staticmethod
    def _monitor_index(display_id: str) -> int:
        if display_id == "primary":
            return 1
        if display_id.startswith("monitor:"):
            try:
                index = int(display_id.partition(":")[2])
            except ValueError as exc:
                raise ValueError("invalid_display_id") from exc
            if index < 1:
                raise ValueError("invalid_display_id")
            return index
        raise ValueError("unsupported_display_id")

    def display_size(self, display_id: str) -> tuple[int, int]:
        """Return the selected monitor's current pixel dimensions."""
        index = self._monitor_index(display_id)
        with self._lock, self._mss.mss() as capture:
            monitors = capture.monitors
            if index >= len(monitors):
                raise ValueError("display_not_found")
            monitor = monitors[index]
            return int(monitor["width"]), int(monitor["height"])

    def capture_screen(self, display_id: str) -> bytes:
        """Capture one monitor to in-memory PNG bytes; no file is written."""
        index = self._monitor_index(display_id)
        with self._lock, self._mss.mss() as capture:
            monitors = capture.monitors
            if index >= len(monitors):
                raise ValueError("display_not_found")
            shot = capture.grab(monitors[index])
            image = self._image.frombytes("RGB", shot.size, shot.rgb)
            buffer = io.BytesIO()
            image.save(buffer, format="PNG")
            return buffer.getvalue()

    def execute_action(self, action: DesktopAction) -> None:
        """Dispatch one typed action; no arbitrary command or script execution."""
        with self._lock:
            mouse = self._pyautogui
            if action.kind == "move":
                mouse.moveTo(action.x, action.y)
            elif action.kind == "click":
                mouse.click(x=action.x, y=action.y, button=action.button)
            elif action.kind == "double_click":
                mouse.doubleClick(x=action.x, y=action.y, button=action.button)
            elif action.kind == "context_click":
                mouse.rightClick(x=action.x, y=action.y)
            elif action.kind == "scroll":
                mouse.scroll(action.scroll_delta, x=action.x, y=action.y)
            elif action.kind == "drag":
                mouse.moveTo(action.x, action.y)
                mouse.dragTo(action.end_x, action.end_y, button=action.button)
            elif action.kind == "keypress":
                if len(action.keys) == 1:
                    mouse.press(action.keys[0])
                    mouse.release(action.keys[0])
                else:
                    mouse.hotkey(*action.keys)
            elif action.kind == "type_text":
                mouse.write(action.text, interval=0.01)
            else:
                raise ValueError("unsupported_desktop_action")
