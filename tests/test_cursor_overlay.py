"""Tests for build_cursor_overlay factory and the null back-end."""

from __future__ import annotations

from unittest.mock import patch

from voxy.config import UIConfig
from voxy.cursor_overlay import (
    _NullCursorOverlay,
    build_cursor_overlay,
)


def test_disabled_returns_null() -> None:
    config = UIConfig(cursor_overlay=False)
    overlay = build_cursor_overlay(config)
    assert isinstance(overlay, _NullCursorOverlay)


def test_null_back_end_is_silent() -> None:
    overlay = _NullCursorOverlay()
    overlay.show()
    overlay.processing()
    overlay.hide()
    overlay.stop()


def test_wayland_without_hyprland_falls_back(capsys) -> None:
    config = UIConfig(cursor_overlay=True)
    env = {"WAYLAND_DISPLAY": "wayland-0"}
    with patch.dict("os.environ", env, clear=True), patch(
        "voxy.cursor_overlay._hyprland_socket_path", return_value=None
    ):
        overlay = build_cursor_overlay(config)
    assert isinstance(overlay, _NullCursorOverlay)
    assert "Hyprland" in capsys.readouterr().err


def test_x11_without_tk_root_falls_back(capsys) -> None:
    config = UIConfig(cursor_overlay=True)
    with patch.dict("os.environ", {}, clear=True):
        overlay = build_cursor_overlay(config, tk_root=None)
    assert isinstance(overlay, _NullCursorOverlay)
    assert "shared Tk root" in capsys.readouterr().err
