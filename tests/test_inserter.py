"""Tests for TextInserter."""

from __future__ import annotations

import subprocess
from typing import Any
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


# ---------------------------------------------------------------------------
# Terminal detection — X11
# ---------------------------------------------------------------------------

def _x11_run_factory(wm_class_output: str, win_id: str = "12345") -> Any:
    """Return a subprocess.run side_effect that simulates X11 terminal detection."""
    def fake_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if cmd[:2] == ["xdotool", "getactivewindow"]:
            return subprocess.CompletedProcess(cmd, 0, stdout=f"{win_id}\n", stderr="")
        if cmd[:2] == ["xprop", "-id"]:
            return subprocess.CompletedProcess(cmd, 0, stdout=wm_class_output, stderr="")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
    return fake_run


def test_x11_terminal_focused_uses_ctrl_shift_v(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DISPLAY", ":0")
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    monkeypatch.delenv("HYPRLAND_INSTANCE_SIGNATURE", raising=False)
    monkeypatch.delenv("SWAYSOCK", raising=False)
    wm_class = 'WM_CLASS(STRING) = "alacritty", "Alacritty"\n'
    with patch("voxy.inserter.subprocess.run", side_effect=_x11_run_factory(wm_class)) as mock_run:
        TextInserter("auto").insert("hello")
    key_calls = [c.args[0] for c in mock_run.call_args_list if c.args[0][:2] == ["xdotool", "key"]]
    assert any("ctrl+shift+v" in c for c in key_calls)


def test_x11_non_terminal_uses_ctrl_v(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DISPLAY", ":0")
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    monkeypatch.delenv("HYPRLAND_INSTANCE_SIGNATURE", raising=False)
    monkeypatch.delenv("SWAYSOCK", raising=False)
    wm_class = 'WM_CLASS(STRING) = "firefox", "Firefox"\n'
    with patch("voxy.inserter.subprocess.run", side_effect=_x11_run_factory(wm_class)) as mock_run:
        TextInserter("auto").insert("hello")
    key_calls = [c.args[0] for c in mock_run.call_args_list if c.args[0][:2] == ["xdotool", "key"]]
    assert any("ctrl+v" in c and "ctrl+shift+v" not in c for c in key_calls)


@pytest.mark.parametrize("wm_class_fragment,label", [
    ("konsole", "konsole"),
    ("gnome-terminal-server", "gnome-terminal"),
    ("alacritty", "alacritty"),
    ("com.mitchellh.ghostty", "ghostty"),
    ("kitty", "kitty"),
])
def test_x11_all_supported_terminals_trigger_ctrl_shift_v(
    monkeypatch: pytest.MonkeyPatch,
    wm_class_fragment: str,
    label: str,
) -> None:
    monkeypatch.setenv("DISPLAY", ":0")
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    monkeypatch.delenv("HYPRLAND_INSTANCE_SIGNATURE", raising=False)
    monkeypatch.delenv("SWAYSOCK", raising=False)
    wm_class = f'WM_CLASS(STRING) = "{wm_class_fragment}", "{wm_class_fragment.capitalize()}"\n'
    with patch("voxy.inserter.subprocess.run", side_effect=_x11_run_factory(wm_class)) as mock_run:
        TextInserter("auto").insert("hello")
    key_calls = [c.args[0] for c in mock_run.call_args_list if c.args[0][:2] == ["xdotool", "key"]]
    assert any("ctrl+shift+v" in c for c in key_calls), f"{label} not recognized as terminal"


def test_x11_detection_failure_falls_back_to_ctrl_v(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DISPLAY", ":0")
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    monkeypatch.delenv("HYPRLAND_INSTANCE_SIGNATURE", raising=False)
    monkeypatch.delenv("SWAYSOCK", raising=False)

    def failing_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if cmd[0] in ("xdotool", "xprop"):
            return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="error")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    with patch("voxy.inserter.subprocess.run", side_effect=failing_run) as mock_run:
        TextInserter("auto").insert("hello")
    key_calls = [c.args[0] for c in mock_run.call_args_list if c.args[0][:2] == ["xdotool", "key"]]
    assert any("ctrl+v" in c and "ctrl+shift+v" not in c for c in key_calls)


# ---------------------------------------------------------------------------
# Terminal detection — Hyprland
# ---------------------------------------------------------------------------

def _wayland_run_factory(
    hyprctl_class: str | None = None,
    sway_tree: str | None = None,
    gdbus_output: str | None = None,
) -> Any:
    """Return a subprocess.run side_effect for Wayland compositor detection."""
    def fake_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if cmd[:2] == ["hyprctl", "activewindow"]:
            out = f'{{"class": "{hyprctl_class}"}}' if hyprctl_class is not None else "{}"
            return subprocess.CompletedProcess(cmd, 0, stdout=out, stderr="")
        if cmd[:2] == ["swaymsg", "-t"]:
            out = sway_tree or "{}"
            return subprocess.CompletedProcess(cmd, 0, stdout=out, stderr="")
        if cmd[0] == "gdbus":
            if gdbus_output is None:
                return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="error")
            return subprocess.CompletedProcess(cmd, 0, stdout=gdbus_output, stderr="")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
    return fake_run


def test_hyprland_terminal_uses_ctrl_shift_v(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HYPRLAND_INSTANCE_SIGNATURE", "abc123")
    monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-1")
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.delenv("SWAYSOCK", raising=False)
    with patch("voxy.inserter.subprocess.run", side_effect=_wayland_run_factory(hyprctl_class="kitty")) as mock_run:
        TextInserter("auto").insert("hello")
    ydotool_calls = [c.args[0] for c in mock_run.call_args_list if c.args[0][0] == "ydotool"]
    assert any("42:1" in c for c in ydotool_calls), "Shift keycode missing — expected ctrl+shift+v"


def test_hyprland_non_terminal_uses_ctrl_v(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HYPRLAND_INSTANCE_SIGNATURE", "abc123")
    monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-1")
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.delenv("SWAYSOCK", raising=False)
    with patch("voxy.inserter.subprocess.run", side_effect=_wayland_run_factory(hyprctl_class="firefox")) as mock_run:
        TextInserter("auto").insert("hello")
    ydotool_calls = [c.args[0] for c in mock_run.call_args_list if c.args[0][0] == "ydotool"]
    assert not any("42:1" in c for c in ydotool_calls), "Shift keycode present — should use ctrl+v"


# ---------------------------------------------------------------------------
# Terminal detection — Sway
# ---------------------------------------------------------------------------

_SWAY_TREE_TERMINAL = """{
  "focused": false,
  "nodes": [{
    "focused": true,
    "app_id": "alacritty",
    "nodes": [], "floating_nodes": []
  }],
  "floating_nodes": []
}"""

_SWAY_TREE_NON_TERMINAL = """{
  "focused": false,
  "nodes": [{
    "focused": true,
    "app_id": "firefox",
    "nodes": [], "floating_nodes": []
  }],
  "floating_nodes": []
}"""


def test_sway_terminal_uses_ctrl_shift_v(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SWAYSOCK", "/run/user/1000/sway-ipc.sock")
    monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-1")
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.delenv("HYPRLAND_INSTANCE_SIGNATURE", raising=False)
    with patch("voxy.inserter.subprocess.run", side_effect=_wayland_run_factory(sway_tree=_SWAY_TREE_TERMINAL)) as mock_run:
        TextInserter("auto").insert("hello")
    ydotool_calls = [c.args[0] for c in mock_run.call_args_list if c.args[0][0] == "ydotool"]
    assert any("42:1" in c for c in ydotool_calls), "Shift keycode missing — expected ctrl+shift+v"


def test_sway_non_terminal_uses_ctrl_v(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SWAYSOCK", "/run/user/1000/sway-ipc.sock")
    monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-1")
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.delenv("HYPRLAND_INSTANCE_SIGNATURE", raising=False)
    with patch("voxy.inserter.subprocess.run", side_effect=_wayland_run_factory(sway_tree=_SWAY_TREE_NON_TERMINAL)) as mock_run:
        TextInserter("auto").insert("hello")
    ydotool_calls = [c.args[0] for c in mock_run.call_args_list if c.args[0][0] == "ydotool"]
    assert not any("42:1" in c for c in ydotool_calls), "Shift keycode present — should use ctrl+v"


# ---------------------------------------------------------------------------
# Terminal detection — GNOME Wayland
# ---------------------------------------------------------------------------

def test_gnome_wayland_terminal_uses_ctrl_shift_v(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_CURRENT_DESKTOP", "GNOME")
    monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-1")
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.delenv("HYPRLAND_INSTANCE_SIGNATURE", raising=False)
    monkeypatch.delenv("SWAYSOCK", raising=False)
    gdbus_out = "(true, 'Alacritty')\n"
    with patch("voxy.inserter.subprocess.run", side_effect=_wayland_run_factory(gdbus_output=gdbus_out)) as mock_run:
        TextInserter("auto").insert("hello")
    ydotool_calls = [c.args[0] for c in mock_run.call_args_list if c.args[0][0] == "ydotool"]
    assert any("42:1" in c for c in ydotool_calls), "Shift keycode missing — expected ctrl+shift+v"


def test_gnome_wayland_gdbus_failure_falls_back_to_ctrl_v(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_CURRENT_DESKTOP", "GNOME")
    monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-1")
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.delenv("HYPRLAND_INSTANCE_SIGNATURE", raising=False)
    monkeypatch.delenv("SWAYSOCK", raising=False)
    with patch("voxy.inserter.subprocess.run", side_effect=_wayland_run_factory(gdbus_output=None)) as mock_run:
        TextInserter("auto").insert("hello")
    ydotool_calls = [c.args[0] for c in mock_run.call_args_list if c.args[0][0] == "ydotool"]
    assert not any("42:1" in c for c in ydotool_calls), "Shift keycode present — should use ctrl+v"
