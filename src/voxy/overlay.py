"""OverlayUI — floating indicator window."""

from __future__ import annotations

import queue
import sys
import time
import tkinter as tk

from .config import UIConfig

_WIDTH = 80
_HEIGHT = 28

_COLORS: dict[str, str] = {
    "recording": "#ff4444",
    "processing": "#ffaa00",
}
_LABELS: dict[str, str] = {
    "recording": "REC",
    "processing": "…",
}


class OverlayUI:
    """A small borderless floating window to indicate recording state."""

    _config: UIConfig
    _root: tk.Tk | None
    _label: tk.Label | None
    _queue: queue.Queue[str]

    def __init__(self, config: UIConfig) -> None:
        self._config = config
        self._root = None
        self._label = None
        self._queue: queue.Queue[str] = queue.Queue()
        if self._config.overlay:
            try:
                self._root = tk.Tk()
            except tk.TclError as exc:
                print(f"voxy: overlay disabled — {exc}", file=sys.stderr)
                return
            self._root.withdraw()
            try:
                self._root.overrideredirect(True)
                self._root.attributes("-topmost", True)
            except tk.TclError:
                pass
            self._root.configure(bg=_COLORS["recording"])
            self._label = tk.Label(
                self._root,
                text=_LABELS["recording"],
                bg=_COLORS["recording"],
                fg="white",
                font=("sans-serif", 10, "bold"),
            )
            self._label.pack(expand=True)

    def show(self) -> None:
        if not self._root:
            return
        self._queue.put("show")

    def processing(self) -> None:
        if not self._root:
            return
        self._queue.put("processing")

    def hide(self) -> None:
        if not self._root:
            return
        self._queue.put("hide")

    def _poll(self) -> None:
        try:
            while True:
                cmd = self._queue.get_nowait()
                if cmd == "show":
                    self._apply_state("recording")
                    self._show_internal()
                elif cmd == "processing":
                    self._apply_state("processing")
                elif cmd == "hide":
                    self._hide_internal()
        except queue.Empty:
            pass
        except tk.TclError:
            pass
        if self._root:
            self._root.after(50, self._poll)

    def _apply_state(self, state: str) -> None:
        if not self._root or not self._label:
            return
        color = _COLORS[state]
        self._root.configure(bg=color)
        self._label.configure(bg=color, text=_LABELS[state])

    def _show_internal(self) -> None:
        if not self._root:
            return
        margin = 20
        sw = self._root.winfo_screenwidth()
        sh = self._root.winfo_screenheight()

        corner = self._config.overlay_corner
        if corner == "bottom-right":
            x = sw - _WIDTH - margin
            y = sh - _HEIGHT - margin
        elif corner == "top-left":
            x = margin
            y = margin
        elif corner == "top-right":
            x = sw - _WIDTH - margin
            y = margin
        elif corner == "bottom-left":
            x = margin
            y = sh - _HEIGHT - margin
        else:
            x = sw - _WIDTH - margin
            y = sh - _HEIGHT - margin

        self._root.geometry(f"{_WIDTH}x{_HEIGHT}+{x}+{y}")
        self._root.deiconify()
        self._root.update()

    def _hide_internal(self) -> None:
        if not self._root:
            return
        self._root.withdraw()
        self._root.update()

    def wait_loop(self) -> None:
        """Pump UI events until interrupted."""
        if not self._root:
            return
        self._poll()
        try:
            while True:
                self._root.update()
                time.sleep(0.05)
        except tk.TclError:
            pass
