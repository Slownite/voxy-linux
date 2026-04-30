"""OverlayUI — floating indicator window."""

from __future__ import annotations

import queue
import time
import tkinter as tk

from .config import UIConfig


class OverlayUI:
    """A small borderless floating window to indicate recording state."""

    _config: UIConfig
    _root: tk.Tk | None
    _queue: queue.Queue[str]

    def __init__(self, config: UIConfig) -> None:
        self._config = config
        self._root = None
        self._queue: queue.Queue[str] = queue.Queue()
        if self._config.overlay:
            self._root = tk.Tk()
            self._root.withdraw()
            try:
                self._root.overrideredirect(True)
                self._root.attributes("-topmost", True)
            except tk.TclError:
                pass
            self._root.configure(bg="#ff4444")

    def show(self) -> None:
        if not self._root:
            return
        self._queue.put("show")

    def hide(self) -> None:
        if not self._root:
            return
        self._queue.put("hide")

    def _poll(self) -> None:
        try:
            while True:
                cmd = self._queue.get_nowait()
                if cmd == "show":
                    self._show_internal()
                elif cmd == "hide":
                    self._hide_internal()
        except queue.Empty:
            pass
        if self._root:
            self._root.after(50, self._poll)

    def _show_internal(self) -> None:
        if not self._root:
            return
        size = 24
        margin = 20
        sw = self._root.winfo_screenwidth()
        sh = self._root.winfo_screenheight()

        corner = self._config.overlay_corner
        if corner == "bottom-right":
            x = sw - size - margin
            y = sh - size - margin
        elif corner == "top-left":
            x = margin
            y = margin
        elif corner == "top-right":
            x = sw - size - margin
            y = margin
        elif corner == "bottom-left":
            x = margin
            y = sh - size - margin
        else:
            x = sw - size - margin
            y = sh - size - margin

        self._root.geometry(f"{size}x{size}+{x}+{y}")
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
