"""TextInserter — clipboard + paste for X11 and Wayland."""

from __future__ import annotations

import json
import os
import shutil
import subprocess

_DETECT_TIMEOUT: float = 0.5  # seconds — detection must not block the insert flow

_TERMINAL_CLASSES: frozenset[str] = frozenset({
    "konsole", "org.kde.konsole",
    "gnome-terminal", "gnome-terminal-server", "org.gnome.terminal",
    "alacritty",
    "ghostty", "com.mitchellh.ghostty",
    "kitty",
})

# ydotool keycodes: 29=Ctrl, 42=Shift, 47=V
_YDOTOOL_CTRL_V: list[str] = ["29:1", "47:1", "47:0", "29:0"]
_YDOTOOL_CTRL_SHIFT_V: list[str] = ["29:1", "42:1", "47:1", "47:0", "42:0", "29:0"]


def check_tools(method: str = "auto") -> None:
    """Raise RuntimeError with install instructions if required tools are missing."""
    if method == "auto":
        if os.environ.get("WAYLAND_DISPLAY"):
            method = "wayland"
        elif os.environ.get("DISPLAY"):
            method = "x11"
        else:
            return  # display detection will fail later with its own message

    if method == "wayland":
        missing = [t for t in ("wl-copy", "ydotool") if not shutil.which(t)]
        if missing:
            raise RuntimeError(
                f"voxy requires {' and '.join(missing)} for Wayland text insertion.\n"
                "  Fix: sudo pacman -S wl-clipboard ydotool\n"
                "  Then enable the daemon: systemctl --user enable --now ydotool"
            )
    elif method == "x11":
        missing = [t for t in ("xclip", "xdotool") if not shutil.which(t)]
        if missing:
            raise RuntimeError(
                f"voxy requires {' and '.join(missing)} for X11 text insertion.\n"
                "  Fix: sudo pacman -S xclip xdotool"
            )


_NOTIFY_PREVIEW_LIMIT: int = 200


class TextInserter:
    _method: str
    _notify: bool

    def __init__(self, method: str = "auto", notify: bool = True) -> None:
        self._method = method
        self._notify = notify

    def _backend(self) -> str:
        if self._method != "auto":
            return self._method
        if os.environ.get("WAYLAND_DISPLAY"):
            return "wayland"
        if os.environ.get("DISPLAY"):
            return "x11"
        raise RuntimeError(
            "Cannot detect display server. Set $DISPLAY (X11) or $WAYLAND_DISPLAY (Wayland), "
            "or set insertion.method in config."
        )

    def _focused_class(self) -> str:
        """Return the lowercase WM_CLASS / app_id of the focused window, or ''."""
        if os.environ.get("HYPRLAND_INSTANCE_SIGNATURE"):
            return self._focused_class_hyprland()
        if os.environ.get("SWAYSOCK"):
            return self._focused_class_sway()
        # GNOME native Wayland without XWayland: try gdbus before xdotool
        if (
            os.environ.get("XDG_CURRENT_DESKTOP", "").lower() == "gnome"
            and os.environ.get("WAYLAND_DISPLAY")
            and not os.environ.get("DISPLAY")
        ):
            return self._focused_class_gnome_wayland()
        if os.environ.get("DISPLAY"):
            return self._focused_class_x11()
        # GNOME Wayland with XWayland present: xdotool already tried above;
        # fall back to gdbus for native Wayland apps that xdotool can't see
        if (
            os.environ.get("XDG_CURRENT_DESKTOP", "").lower() == "gnome"
            and os.environ.get("WAYLAND_DISPLAY")
        ):
            return self._focused_class_gnome_wayland()
        return ""

    def _focused_class_x11(self) -> str:
        try:
            win = subprocess.run(
                ["xdotool", "getactivewindow"],
                capture_output=True, text=True, check=False,
                timeout=_DETECT_TIMEOUT,
            )
            if win.returncode != 0 or not win.stdout.strip():
                return ""
            xprop = subprocess.run(
                ["xprop", "-id", win.stdout.strip(), "WM_CLASS"],
                capture_output=True, text=True, check=False,
                timeout=_DETECT_TIMEOUT,
            )
            if xprop.returncode != 0:
                return ""
            return xprop.stdout.lower()
        except (subprocess.TimeoutExpired, OSError):
            return ""

    def _focused_class_hyprland(self) -> str:
        try:
            result = subprocess.run(
                ["hyprctl", "activewindow", "-j"],
                capture_output=True, text=True, check=False,
                timeout=_DETECT_TIMEOUT,
            )
            if result.returncode != 0:
                return ""
            data: dict[str, object] = json.loads(result.stdout)
            cls = data.get("class", "")
            return str(cls).lower() if cls else ""
        except (subprocess.TimeoutExpired, OSError, json.JSONDecodeError, KeyError):
            return ""

    def _focused_class_sway(self) -> str:
        try:
            result = subprocess.run(
                ["swaymsg", "-t", "get_tree"],
                capture_output=True, text=True, check=False,
                timeout=_DETECT_TIMEOUT,
            )
            if result.returncode != 0:
                return ""
            tree: dict[str, object] = json.loads(result.stdout)
            node = _find_focused_sway(tree)
            if node is None:
                return ""
            app_id = node.get("app_id") or node.get("window_properties", {})
            if isinstance(app_id, dict):
                app_id = app_id.get("class", "")
            return str(app_id).lower() if app_id else ""
        except (subprocess.TimeoutExpired, OSError, json.JSONDecodeError, KeyError, AttributeError):
            return ""

    def _focused_class_gnome_wayland(self) -> str:
        try:
            result = subprocess.run(
                [
                    "gdbus", "call", "--session",
                    "--dest", "org.gnome.Shell",
                    "--object-path", "/org/gnome/Shell",
                    "--method", "org.gnome.Shell.Eval",
                    "global.display.get_focus_window().get_wm_class()",
                ],
                capture_output=True, text=True, check=False,
                timeout=_DETECT_TIMEOUT,
            )
            if result.returncode != 0:
                return ""
            # gdbus output: "(true, 'Alacritty')\n"
            out = result.stdout.strip()
            if not out.startswith("(true,"):
                return ""
            return out.split(",", 1)[-1].strip(" ')\"").lower()
        except (subprocess.TimeoutExpired, OSError):
            return ""

    def _is_terminal_focused(self) -> bool:
        try:
            cls = self._focused_class()
            return any(t in cls for t in _TERMINAL_CLASSES)
        except Exception:
            return False

    def insert(self, text: str) -> None:
        backend = self._backend()
        terminal = self._is_terminal_focused()
        if backend == "x11":
            subprocess.run(
                ["xclip", "-selection", "clipboard"],
                input=text.encode(),
                check=False,
            )
            paste_key = "ctrl+shift+v" if terminal else "ctrl+v"
            subprocess.run(
                ["xdotool", "key", "--clearmodifiers", paste_key],
                check=False,
            )
        else:
            subprocess.run(["wl-copy", text], check=False)
            keycodes = _YDOTOOL_CTRL_SHIFT_V if terminal else _YDOTOOL_CTRL_V
            subprocess.run(["ydotool", "key", *keycodes], check=False)
        self._notify_copied(text)

    def _notify_copied(self, text: str) -> None:
        if not self._notify or not text:
            return
        if not shutil.which("notify-send"):
            return
        preview = text if len(text) <= _NOTIFY_PREVIEW_LIMIT else text[:_NOTIFY_PREVIEW_LIMIT - 1] + "…"
        subprocess.Popen(
            [
                "notify-send",
                "-a", "voxy",
                "-t", "2000",
                "-i", "edit-paste",
                "voxy: copied to clipboard",
                preview,
            ],
        )


def _find_focused_sway(node: object) -> dict[str, object] | None:
    if not isinstance(node, dict):
        return None
    if node.get("focused"):
        return node
    for child in list(node.get("nodes", [])) + list(node.get("floating_nodes", [])):
        found = _find_focused_sway(child)
        if found is not None:
            return found
    return None
