"""Platform guard tests for the optional Windows desktop adapter."""

import pytest

from mehr_ai_studio import windows_desktop


def test_windows_adapter_refuses_non_windows_platform(monkeypatch):
    monkeypatch.setattr(windows_desktop.sys, "platform", "linux")
    with pytest.raises(RuntimeError, match="requires_windows"):
        windows_desktop.WindowsDesktopAdapter()


def test_monitor_id_parser_accepts_only_explicit_monitor_ids():
    parser = windows_desktop.WindowsDesktopAdapter._monitor_index
    assert parser("primary") == 1
    assert parser("monitor:2") == 2
    with pytest.raises(ValueError, match="invalid_display_id"):
        parser("monitor:0")
    with pytest.raises(ValueError, match="unsupported_display_id"):
        parser("all")


class FakeCapture:
    monitors = [
        {"left": 0, "top": 0, "width": 3000, "height": 1200},
        {"left": -1920, "top": 0, "width": 1920, "height": 1080},
        {"left": 0, "top": 0, "width": 1920, "height": 1080},
    ]

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False


class FakeMss:
    @staticmethod
    def mss():
        return FakeCapture()


def test_monitor_relative_coordinates_translate_to_virtual_desktop():
    adapter = object.__new__(windows_desktop.WindowsDesktopAdapter)
    adapter._mss = FakeMss
    assert adapter._absolute_point(25, 40, "monitor:1") == (-1895, 40)
    assert adapter._absolute_point(25, 40, "monitor:2") == (25, 40)
