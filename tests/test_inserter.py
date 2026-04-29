"""Tests for TextInserter."""

from __future__ import annotations

from unittest.mock import call, patch

import pytest

from voxy.inserter import TextInserter


def test_auto_x11_uses_xclip_and_xdotool(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DISPLAY", ":0")
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    with patch("voxy.inserter.subprocess.run") as mock_run:
        TextInserter("auto").insert("hello")
    calls = [c.args[0] for c in mock_run.call_args_list]
    assert any("xclip" in c for c in calls)
    assert any("xdotool" in c for c in calls)


def test_auto_wayland_uses_wlcopy_and_ydotool(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
    with patch("voxy.inserter.subprocess.run") as mock_run:
        TextInserter("auto").insert("hello")
    calls = [c.args[0] for c in mock_run.call_args_list]
    assert any("wl-copy" in c for c in calls)
    assert any("ydotool" in c for c in calls)


def test_auto_prefers_wayland_when_both_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DISPLAY", ":0")
    monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
    with patch("voxy.inserter.subprocess.run") as mock_run:
        TextInserter("auto").insert("hello")
    calls = [c.args[0] for c in mock_run.call_args_list]
    assert any("wl-copy" in c for c in calls)
    assert any("ydotool" in c for c in calls)


def test_auto_no_display_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    with pytest.raises(RuntimeError, match="display server"):
        TextInserter("auto").insert("hello")


def test_override_x11_ignores_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
    with patch("voxy.inserter.subprocess.run") as mock_run:
        TextInserter("x11").insert("hello")
    calls = [c.args[0] for c in mock_run.call_args_list]
    assert any("xclip" in c for c in calls)
    assert any("xdotool" in c for c in calls)


def test_override_wayland_ignores_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DISPLAY", ":0")
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    with patch("voxy.inserter.subprocess.run") as mock_run:
        TextInserter("wayland").insert("hello")
    calls = [c.args[0] for c in mock_run.call_args_list]
    assert any("wl-copy" in c for c in calls)
    assert any("ydotool" in c for c in calls)


def test_x11_passes_text_to_clipboard(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DISPLAY", ":0")
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    with patch("voxy.inserter.subprocess.run") as mock_run:
        TextInserter("auto").insert("type this")
    xclip_call = next(c for c in mock_run.call_args_list if "xclip" in c.args[0])
    assert xclip_call.kwargs["input"] == b"type this"


def test_wayland_passes_text_to_clipboard(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
    with patch("voxy.inserter.subprocess.run") as mock_run:
        TextInserter("auto").insert("type this")
    wlcopy_call = next(c for c in mock_run.call_args_list if "wl-copy" in c.args[0])
    assert "type this" in wlcopy_call.args[0]
