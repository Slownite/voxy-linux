"""TextInserter — clipboard + paste for X11 and Wayland."""

from __future__ import annotations

import os
import subprocess


class TextInserter:
    _method: str

    def __init__(self, method: str = "auto") -> None:
        self._method = method

    def _backend(self) -> str:
        if self._method != "auto":
            return self._method
        if os.environ.get("DISPLAY"):
            return "x11"
        if os.environ.get("WAYLAND_DISPLAY"):
            return "wayland"
        raise RuntimeError(
            "Cannot detect display server. Set $DISPLAY (X11) or $WAYLAND_DISPLAY (Wayland), "
            "or set insertion.method in config."
        )

    def insert(self, text: str) -> None:
        backend = self._backend()
        if backend == "x11":
            subprocess.run(
                ["xclip", "-selection", "clipboard"],
                input=text.encode(),
                check=False,
            )
            subprocess.run(
                ["xdotool", "key", "--clearmodifiers", "ctrl+v"],
                check=False,
            )
        else:
            subprocess.run(["wl-copy", text], check=False)
            subprocess.run(["ydotool", "key", "29:1", "47:1", "47:0", "29:0"], check=False)
