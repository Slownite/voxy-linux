"""CursorOverlay — optional indicator anchored to the mouse cursor.

See [docs/adr/0001-cursor-overlay.md] for the design.

Back-ends:
- `_X11CursorOverlay`      — Tk + pynput (X11 / XWayland).
- `_WaylandCursorOverlay`  — GTK4 + gtk4-layer-shell + Hyprland IPC socket.
- `_NullCursorOverlay`     — no-op fallback.

`build_cursor_overlay(config, tk_root)` selects by env inspection.
Protocol mirrors `OverlayUI`: show() → processing() → hide().
"""

from __future__ import annotations

import logging
import os
import queue
import socket
import sys
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    import tkinter as tk

from .config import UIConfig

_log = logging.getLogger(__name__)

_FRAME_SIZE = 80
_FRAME_STROKE = 3
_RECT_W = 90
_RECT_H = 22
_RECT_OFFSET = 24
_THROTTLE_S = 1 / 60

_COLOR_RECORDING  = "#22cc55"
_COLOR_PROCESSING = "#ffaa00"
_COLOR_RECORDING_RGB  = (0.13, 0.80, 0.33)
_COLOR_PROCESSING_RGB = (1.0,  0.67, 0.0)
_LABELS = {"recording": "REC", "processing": "PROCESSING"}


class CursorOverlay(Protocol):
    def show(self) -> None: ...
    def processing(self) -> None: ...
    def hide(self) -> None: ...
    def stop(self) -> None: ...


class _NullCursorOverlay:
    def show(self) -> None: return
    def processing(self) -> None: return
    def hide(self) -> None: return
    def stop(self) -> None: return


# ---------------------------------------------------------------------------
# X11 back-end
# ---------------------------------------------------------------------------

class _X11CursorOverlay:
    """Tk-based cursor overlay for X11 / XWayland.

    4 thin Toplevel strips form a square contour around the cursor.
    5th Toplevel is a canvas-drawn status rect (stroke + text, no fill).
    pynput mouse.Listener feeds (x, y) into a queue drained by Tk after().
    Throttled to ~60 Hz to avoid flooding X11 with ConfigureWindow calls.
    """

    def __init__(self, root: Any) -> None:
        import tkinter as tk  # noqa: PLC0415
        self._tk = tk
        self._root = root
        self._queue: queue.Queue[tuple[str, Any]] = queue.Queue()
        self._listener: Any = None
        self._visible = False
        self._state = "recording"
        self._last_pos = (0, 0)
        self._last_apply = 0.0
        self._strips: list[Any] = []
        self._rect: Any = None
        self._rect_canvas: Any = None
        self._build_windows()
        self._root.after(16, self._poll)

    def _build_windows(self) -> None:
        tk = self._tk
        for _ in range(4):
            w = tk.Toplevel(self._root)
            w.withdraw()
            try:
                w.overrideredirect(True)
                w.attributes("-topmost", True)
            except self._tk.TclError:
                pass
            w.configure(bg=_COLOR_RECORDING)
            self._strips.append(w)

        _TRANSPARENT = "#010101"
        rect = tk.Toplevel(self._root)
        rect.withdraw()
        try:
            rect.overrideredirect(True)
            rect.attributes("-topmost", True)
            rect.attributes("-transparentcolor", _TRANSPARENT)
        except self._tk.TclError:
            pass
        rect.configure(bg=_TRANSPARENT)
        canvas = tk.Canvas(
            rect,
            width=_RECT_W,
            height=_RECT_H,
            bg=_TRANSPARENT,
            highlightthickness=0,
            bd=0,
        )
        canvas.pack()
        canvas.create_rectangle(
            1, 1, _RECT_W - 1, _RECT_H - 1,
            outline=_COLOR_RECORDING, fill=_TRANSPARENT, width=_FRAME_STROKE,
            tags="border",
        )
        canvas.create_text(
            _RECT_W // 2, _RECT_H // 2,
            text=_LABELS["recording"],
            fill=_COLOR_RECORDING,
            font=("sans-serif", 9, "bold"),
            tags="label",
        )
        self._rect = rect
        self._rect_canvas = canvas

    def show(self) -> None:
        self._queue.put(("state", "recording"))
        self._queue.put(("show", None))
        self._start_listener()

    def processing(self) -> None:
        self._queue.put(("state", "processing"))

    def hide(self) -> None:
        self._queue.put(("hide", None))
        self._stop_listener()

    def stop(self) -> None:
        self._stop_listener()

    def _start_listener(self) -> None:
        if self._listener is not None:
            return
        try:
            from pynput import mouse  # noqa: PLC0415
        except ImportError:
            return
        try:
            self._root.update_idletasks()
            x = self._root.winfo_pointerx()
            y = self._root.winfo_pointery()
            self._queue.put(("move", (x, y)))
        except self._tk.TclError:
            pass

        def on_move(x: int, y: int) -> None:
            self._queue.put(("move", (int(x), int(y))))

        try:
            self._listener = mouse.Listener(on_move=on_move)
            self._listener.start()
        except Exception as exc:
            _log.debug("voxy: pynput mouse listener failed (%s)", exc)
            self._listener = None

    def _stop_listener(self) -> None:
        if self._listener is None:
            return
        try:
            self._listener.stop()
        except Exception:
            pass
        self._listener = None

    def _poll(self) -> None:
        pending_move: tuple[int, int] | None = None
        try:
            while True:
                cmd, payload = self._queue.get_nowait()
                if cmd == "move":
                    pending_move = payload
                elif cmd == "show":
                    self._visible = True
                    self._show_internal()
                elif cmd == "hide":
                    self._visible = False
                    self._hide_internal()
                elif cmd == "state":
                    self._state = payload
                    self._apply_state()
        except queue.Empty:
            pass
        except self._tk.TclError:
            return

        if pending_move is not None and self._visible:
            now = time.monotonic()
            if now - self._last_apply >= _THROTTLE_S:
                self._last_pos = pending_move
                self._reposition()
                self._last_apply = now
            else:
                self._queue.put(("move", pending_move))

        try:
            self._root.after(16, self._poll)
        except self._tk.TclError:
            return

    def _apply_state(self) -> None:
        color = _COLOR_RECORDING if self._state == "recording" else _COLOR_PROCESSING
        for s in self._strips:
            try:
                s.configure(bg=color)
            except self._tk.TclError:
                pass
        if self._rect_canvas:
            try:
                self._rect_canvas.itemconfigure("border", outline=color)
                self._rect_canvas.itemconfigure("label", fill=color, text=_LABELS[self._state])
            except self._tk.TclError:
                pass

    def _show_internal(self) -> None:
        self._apply_state()
        for s in self._strips:
            try:
                s.deiconify()
            except self._tk.TclError:
                pass
        if self._rect:
            try:
                self._rect.deiconify()
            except self._tk.TclError:
                pass
        self._reposition()

    def _hide_internal(self) -> None:
        for s in self._strips:
            try:
                s.withdraw()
            except self._tk.TclError:
                pass
        if self._rect:
            try:
                self._rect.withdraw()
            except self._tk.TclError:
                pass

    def _reposition(self) -> None:
        x, y = self._last_pos
        half = _FRAME_SIZE // 2
        layouts = [
            (_FRAME_SIZE, _FRAME_STROKE, x - half, y - half),
            (_FRAME_SIZE, _FRAME_STROKE, x - half, y + half - _FRAME_STROKE),
            (_FRAME_STROKE, _FRAME_SIZE, x - half, y - half),
            (_FRAME_STROKE, _FRAME_SIZE, x + half - _FRAME_STROKE, y - half),
        ]
        for strip, (w, h, sx, sy) in zip(self._strips, layouts, strict=True):
            try:
                strip.geometry(f"{w}x{h}+{sx}+{sy}")
            except self._tk.TclError:
                pass

        if self._rect:
            sw = self._root.winfo_screenwidth()
            sh = self._root.winfo_screenheight()
            rx = x + _RECT_OFFSET
            ry = y + _RECT_OFFSET
            if rx + _RECT_W > sw:
                rx = x - _RECT_OFFSET - _RECT_W
            if ry + _RECT_H > sh:
                ry = y - _RECT_OFFSET - _RECT_H
            try:
                self._rect.geometry(f"{_RECT_W}x{_RECT_H}+{rx}+{ry}")
            except self._tk.TclError:
                pass


# ---------------------------------------------------------------------------
# Hyprland IPC helpers
# ---------------------------------------------------------------------------

def _hyprland_socket_path() -> str | None:
    runtime = os.environ.get("XDG_RUNTIME_DIR")
    if not runtime:
        return None
    sig = os.environ.get("HYPRLAND_INSTANCE_SIGNATURE")
    if sig:
        candidate = Path(runtime) / "hypr" / sig / ".socket.sock"
        if candidate.exists():
            return str(candidate)
    base = Path(runtime) / "hypr"
    if not base.is_dir():
        return None
    candidates = sorted(
        (p for p in base.iterdir() if (p / ".socket.sock").exists()),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return str(candidates[0] / ".socket.sock") if candidates else None


def _hyprland_cursorpos(sock_path: str) -> tuple[int, int] | None:
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(0.1)
    try:
        s.connect(sock_path)
        s.sendall(b"cursorpos")
        raw = s.recv(64).decode("utf-8", "replace").strip()
        x_s, y_s = raw.split(",", 1)
        return int(x_s.strip()), int(y_s.strip())
    except (OSError, ValueError):
        return None
    finally:
        s.close()


# ---------------------------------------------------------------------------
# Wayland back-end
# ---------------------------------------------------------------------------

class _WaylandCursorOverlay:
    """GTK4 + gtk4-layer-shell overlay, one window per monitor.

    One persistent transparent window is created per GDK monitor at startup,
    each pinned to its output via set_monitor(). All windows stay mapped at
    all times — only the one whose output contains the cursor draws anything.
    No surface remap on monitor crossing means zero-flash transitions.

    Hyprland cursorpos returns global logical coords. Each window knows its
    monitor's GDK geometry offset; drawing subtracts that offset.
    """

    def __init__(self, sock_path: str) -> None:
        import gi  # noqa: PLC0415
        gi.require_version("Gtk", "4.0")
        gi.require_version("Gtk4LayerShell", "1.0")
        from gi.repository import GLib, Gtk, Gtk4LayerShell  # noqa: PLC0415

        self._GLib = GLib
        self._Gtk = Gtk
        self._LayerShell = Gtk4LayerShell
        self._sock_path = sock_path

        self._visible = False
        self._state = "recording"
        self._cursor_xy: tuple[int, int] = (-9999, -9999)  # invalid until first poll
        # List of (window, area, offset_x, offset_y, bounds_x, bounds_y, bounds_w, bounds_h)
        # one entry per GDK monitor, filled in _on_activate.
        self._outputs: list[dict[str, Any]] = []
        self._timeout_id: int | None = None
        self._app: Any = None
        self._ready = threading.Event()

        t = threading.Thread(target=self._run_gtk, daemon=True)
        t.start()
        self._ready.wait(timeout=5.0)

    def _run_gtk(self) -> None:
        self._app = self._Gtk.Application(application_id="com.voxy.cursor_overlay")
        self._app.connect("activate", self._on_activate)
        try:
            self._app.run([])
        except Exception as exc:  # pragma: no cover
            _log.debug("voxy: GTK loop exited (%s)", exc)
            self._ready.set()

    def _on_activate(self, _app: Any) -> None:
        try:
            from gi.repository import Gdk  # noqa: PLC0415
            display = Gdk.Display.get_default()
            mlist = display.get_monitors() if display else None
            n = mlist.get_n_items() if mlist else 0
            for i in range(n):
                mon = mlist.get_item(i)
                geo = mon.get_geometry()
                out = {
                    "win": None, "area": None,
                    "ox": geo.x, "oy": geo.y,
                    "bx": geo.x, "by": geo.y, "bw": geo.width, "bh": geo.height,
                    "was_active": False,
                    "linger": 0,  # frames to keep drawing after cursor leaves
                }
                self._build_window(mon, out)
                self._outputs.append(out)
        except Exception as exc:
            _log.debug("voxy: overlay init failed (%s)", exc)
        finally:
            self._ready.set()

    def _build_window(self, monitor: Any, out: dict[str, Any]) -> None:
        import cairo  # noqa: PLC0415
        Gtk = self._Gtk
        LS = self._LayerShell

        win = Gtk.ApplicationWindow(application=self._app)
        LS.init_for_window(win)
        LS.set_layer(win, LS.Layer.TOP)
        LS.set_keyboard_mode(win, LS.KeyboardMode.NONE)
        for edge in (LS.Edge.TOP, LS.Edge.BOTTOM, LS.Edge.LEFT, LS.Edge.RIGHT):
            LS.set_anchor(win, edge, True)
        LS.set_exclusive_zone(win, -1)
        LS.set_monitor(win, monitor)

        css = Gtk.CssProvider()
        css.load_from_data(b"window { background: transparent; }")
        Gtk.StyleContext.add_provider_for_display(
            win.get_display(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        area = Gtk.DrawingArea()
        area.set_draw_func(self._make_draw(out), None)
        win.set_child(area)
        win.set_decorated(False)

        def on_realize(_w: Any) -> None:
            try:
                gdk_surface = win.get_surface()
                if gdk_surface is not None:
                    gdk_surface.set_input_region(cairo.Region())
            except Exception as exc:
                _log.debug("voxy: input region failed (%s)", exc)

        win.connect("realize", on_realize)
        win.present()
        out["win"] = win
        out["area"] = area

    def _make_draw(self, out: dict[str, Any]):  # type: ignore[return]
        """Return a draw function closed over this output's offset."""
        def _draw(_area: Any, cr: Any, w: int, h: int, _data: Any) -> None:
            import cairo  # noqa: PLC0415
            cr.save()
            cr.set_operator(cairo.Operator.CLEAR)
            cr.paint()
            cr.restore()

            if not self._visible:
                return

            gx, gy = self._cursor_xy
            # Draw on the output containing the cursor, or while lingering.
            on_this_output = (out["bx"] <= gx < out["bx"] + out["bw"]
                              and out["by"] <= gy < out["by"] + out["bh"])
            if not on_this_output and out["linger"] <= 0:
                return

            cr.set_operator(cairo.Operator.OVER)
            x, y = gx - out["ox"], gy - out["oy"]
            rgb = _COLOR_RECORDING_RGB if self._state == "recording" else _COLOR_PROCESSING_RGB

            half = _FRAME_SIZE / 2
            cr.set_source_rgba(*rgb, 1.0)
            cr.set_line_width(_FRAME_STROKE)
            cr.rectangle(x - half, y - half, _FRAME_SIZE, _FRAME_SIZE)
            cr.stroke()

            rx = x + _RECT_OFFSET
            ry = y + _RECT_OFFSET
            if rx + _RECT_W > w:
                rx = x - _RECT_OFFSET - _RECT_W
            if ry + _RECT_H > h:
                ry = y - _RECT_OFFSET - _RECT_H
            cr.set_source_rgba(*rgb, 1.0)
            cr.set_line_width(_FRAME_STROKE)
            cr.rectangle(rx, ry, _RECT_W, _RECT_H)
            cr.stroke()

            cr.select_font_face("sans-serif")
            cr.set_font_size(12)
            text = _LABELS[self._state]
            ext = cr.text_extents(text)
            cr.move_to(
                rx + (_RECT_W - ext.width) / 2,
                ry + (_RECT_H + ext.height) / 2 - 1,
            )
            cr.show_text(text)
        return _draw

    def _tick(self) -> bool:
        if not self._visible:
            return False
        pos = _hyprland_cursorpos(self._sock_path)
        if pos is not None and pos != self._cursor_xy:
            self._cursor_xy = pos
            gx, gy = pos
            for out in self._outputs:
                active = (out["bx"] <= gx < out["bx"] + out["bw"]
                          and out["by"] <= gy < out["by"] + out["bh"])
                if active:
                    out["linger"] = 2  # keep drawing for 2 more frames after leaving
                elif out["linger"] > 0:
                    out["linger"] -= 1
                    active = True  # treat as still active to avoid blank frame
                if active or out["was_active"]:
                    area = out.get("area")
                    if area is not None:
                        area.queue_draw()
                out["was_active"] = active
        return True

    def _ensure_timeout(self) -> None:
        if self._timeout_id is None:
            self._timeout_id = self._GLib.timeout_add(16, self._tick)

    def _drop_timeout(self) -> None:
        if self._timeout_id is not None:
            try:
                self._GLib.source_remove(self._timeout_id)
            except Exception:
                pass
            self._timeout_id = None

    def show(self) -> None:
        def do() -> bool:
            self._state = "recording"
            self._visible = True
            for out in self._outputs:
                area = out.get("area")
                if area is not None:
                    area.queue_draw()
            self._ensure_timeout()
            return False
        self._GLib.idle_add(do)

    def processing(self) -> None:
        def do() -> bool:
            self._state = "processing"
            for out in self._outputs:
                area = out.get("area")
                if area is not None:
                    area.queue_draw()
            return False
        self._GLib.idle_add(do)

    def hide(self) -> None:
        def do() -> bool:
            self._visible = False
            self._drop_timeout()
            for out in self._outputs:
                area = out.get("area")
                if area is not None:
                    area.queue_draw()
            return False
        self._GLib.idle_add(do)

    def stop(self) -> None:
        def do() -> bool:
            self._drop_timeout()
            if self._app is not None:
                self._app.quit()
            return False
        try:
            self._GLib.idle_add(do)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def build_cursor_overlay(
    config: UIConfig, tk_root: Any = None,
) -> CursorOverlay:
    """Return the best available CursorOverlay for the current environment."""
    if not getattr(config, "cursor_overlay", False):
        return _NullCursorOverlay()

    if os.environ.get("WAYLAND_DISPLAY"):
        sock_path = _hyprland_socket_path()
        if not sock_path:
            print("voxy: cursor_overlay requires Hyprland — disabled.", file=sys.stderr)
            return _NullCursorOverlay()
        try:
            return _WaylandCursorOverlay(sock_path)
        except (ImportError, ValueError) as exc:
            print(
                f"voxy: cursor_overlay disabled — install gtk4 + gtk4-layer-shell ({exc})",
                file=sys.stderr,
            )
            return _NullCursorOverlay()

    if tk_root is None:
        print(
            "voxy: cursor_overlay needs [ui] overlay = true (shared Tk root) — disabled.",
            file=sys.stderr,
        )
        return _NullCursorOverlay()
    try:
        return _X11CursorOverlay(tk_root)
    except Exception as exc:
        print(f"voxy: cursor_overlay disabled — {exc}", file=sys.stderr)
        return _NullCursorOverlay()
