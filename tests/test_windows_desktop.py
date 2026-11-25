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
