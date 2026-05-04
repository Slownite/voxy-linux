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

_ARROW_STROKE = 2.0   # stroke width for outlines (X11 and Wayland)
# Status rect
_RECT_W = 90
_RECT_H = 22
_RECT_OFFSET = 26

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

    One transparent Toplevel canvas draws the xcursor outline anchored at the
    cursor hotspot.  A second Toplevel shows the status rect (unchanged).
    Shape changes are detected via XFixes CursorNotify events; falls back
    gracefully to no shape tracking if python-xlib / XFixes is absent.
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

        self._cursor_size = int(os.environ.get("XCURSOR_SIZE", "24"))
        try:
            self._scale = max(1, round(root.winfo_fpixels("1i") / 72))
        except Exception:
            self._scale = 1
        self._cursor_shape = "default"
        self._cursor_outlines: dict[str, Any] = {}
        self._cursor_hot: tuple[float, float] = (0.0, 0.0)
        self._shape_cache: dict[
            tuple[str, int], tuple[dict[str, Any], tuple[float, float]]
        ] = {}
        self._outline_photo: Any = None  # held to prevent GC of PhotoImage

        self._outline_win: Any = None
        self._outline_canvas: Any = None
        self._rect: Any = None
        self._rect_canvas: Any = None

        self._build_windows()
        self._load_shape("default")
        self._start_xfixes_watcher()
        self._root.after(16, self._poll)

    def _build_windows(self) -> None:
        tk = self._tk
        _TRANSPARENT = "#010101"

        outline_win = tk.Toplevel(self._root)
        outline_win.withdraw()
        try:
            outline_win.overrideredirect(True)
            outline_win.attributes("-topmost", True)
            outline_win.attributes("-transparentcolor", _TRANSPARENT)
        except self._tk.TclError:
            pass
        outline_win.configure(bg=_TRANSPARENT)
        outline_canvas = tk.Canvas(
            outline_win,
            width=40, height=40,
            bg=_TRANSPARENT,
            highlightthickness=0, bd=0,
        )
        outline_canvas.pack()
        self._outline_win = outline_win
        self._outline_canvas = outline_canvas

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
            width=_RECT_W, height=_RECT_H,
            bg=_TRANSPARENT,
            highlightthickness=0, bd=0,
        )
        canvas.pack()
        canvas.create_rectangle(
            1, 1, _RECT_W - 1, _RECT_H - 1,
            outline=_COLOR_RECORDING, fill=_TRANSPARENT, width=int(_ARROW_STROKE),
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

    def _load_shape(self, shape_name: str) -> None:
        """Build and cache xcursor outline surfaces for shape_name (both states)."""
        scale = self._scale
        key = (shape_name, scale)
        outlines: dict[str, Any] = {}
        hot: tuple[float, float] = (0.0, 0.0)
        if key in self._shape_cache:
            outlines, hot = self._shape_cache[key]
        else:
            path = _find_xcursor_file(shape_name)
            if path is None and shape_name != "default":
                path = _find_xcursor_file("default")
            if path is None:
                return
            for state, rgb in (
                ("recording", _COLOR_RECORDING_RGB),
                ("processing", _COLOR_PROCESSING_RGB),
            ):
                try:
                    result = _build_cursor_outline(path, self._cursor_size, rgb, scale=scale)
                except ImportError:
                    result = None
                if result is not None:
                    surf, xhot, yhot = result
                    outlines[state] = surf
                    hot = (xhot, yhot)
            self._shape_cache[key] = (outlines, hot)
        self._cursor_hot = hot
        self._cursor_outlines = outlines
        self._cursor_shape = shape_name

    def _start_xfixes_watcher(self) -> None:
        """Start XFixes CursorNotify event thread; silent no-op if unavailable."""
        try:
            from Xlib import display as xdisplay
            from Xlib.ext import xfixes
        except ImportError:
            return
        try:
            dpy = xdisplay.Display()
            root = dpy.screen().root
            dpy.xfixes_select_cursor_input(root, xfixes.XFixesDisplayCursorNotifyMask)
            dpy.flush()
            event_base = dpy.xfixes_event_base
        except Exception as exc:
            _log.debug("voxy: XFixes unavailable (%s) — cursor shape tracking disabled", exc)
            return

        q = self._queue

        def _watch() -> None:
            while True:
                try:
                    ev = dpy.next_event()
                    if ev.type == event_base + xfixes.XFixesCursorNotify:
                        name = dpy.get_atom_name(ev.cursor_name)
                        if name:
                            q.put(("shape", name))
                except Exception as exc:
                    _log.debug("voxy: XFixes watcher stopped (%s)", exc)
                    break

        t = threading.Thread(target=_watch, daemon=True)
        t.start()

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
                elif cmd == "shape":
                    self._load_shape(payload)
                    if self._visible:
                        self._redraw_outline()
        except queue.Empty:
            pass
        except self._tk.TclError:
            return

        if pending_move is not None and self._visible:
            now = time.monotonic()
            if now - self._last_apply >= 1 / 60:
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
        if self._rect_canvas:
            try:
                self._rect_canvas.itemconfigure("border", outline=color)
                self._rect_canvas.itemconfigure("label", fill=color, text=_LABELS[self._state])
            except self._tk.TclError:
                pass
        if self._visible:
            self._redraw_outline()

    def _redraw_outline(self) -> None:
        """Paint current state's xcursor surface (or fallback square) on canvas."""
        import base64  # noqa: PLC0415
        import io  # noqa: PLC0415

        canvas = self._outline_canvas
        if canvas is None:
            return
        try:
            canvas.delete("outline")
        except self._tk.TclError:
            return

        surf = self._cursor_outlines.get(self._state)
        if surf is not None:
            buf = io.BytesIO()
            try:
                surf.write_to_png(buf)
            except Exception:
                surf = None
            else:
                photo = self._tk.PhotoImage(
                    data=base64.b64encode(buf.getvalue()).decode()
                )
                if self._scale > 1:
                    photo = photo.subsample(self._scale, self._scale)
                self._outline_photo = photo  # prevent GC
                try:
                    canvas.create_image(0, 0, anchor="nw", image=photo, tags="outline")
                except self._tk.TclError:
                    pass
                return

        # Fallback: draw a plain square on the canvas.
        _SZ = 40
        color = _COLOR_RECORDING if self._state == "recording" else _COLOR_PROCESSING
        try:
            canvas.config(width=_SZ, height=_SZ)
            canvas.create_rectangle(
                2, 2, _SZ - 2, _SZ - 2,
                outline=color, fill="#010101", width=2, tags="outline",
            )
        except self._tk.TclError:
            pass

    def _show_internal(self) -> None:
        self._apply_state()
        self._redraw_outline()
        if self._outline_win:
            try:
                self._outline_win.deiconify()
            except self._tk.TclError:
                pass
        if self._rect:
            try:
                self._rect.deiconify()
            except self._tk.TclError:
                pass
        self._reposition()

    def _hide_internal(self) -> None:
        if self._outline_win:
            try:
                self._outline_win.withdraw()
            except self._tk.TclError:
                pass
        if self._rect:
            try:
                self._rect.withdraw()
            except self._tk.TclError:
                pass

    def _reposition(self) -> None:
        x, y = self._last_pos
        xhot, yhot = self._cursor_hot
        surf = self._cursor_outlines.get(self._state)

        if surf is not None:
            phys_w = surf.get_width()
            phys_h = surf.get_height()
            log_w = max(1, phys_w // self._scale)
            log_h = max(1, phys_h // self._scale)
            wx = x - int(xhot)
            wy = y - int(yhot)
        else:
            _SZ = 40
            log_w, log_h = _SZ, _SZ
            wx = x - _SZ // 2
            wy = y - _SZ // 2

        if self._outline_win and self._outline_canvas:
            try:
                self._outline_canvas.config(width=log_w, height=log_h)
                self._outline_win.geometry(f"{log_w}x{log_h}+{wx}+{wy}")
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


_PLUGIN_SO = Path.home() / ".local" / "share" / "hyprland" / "plugins" / "cursor-shape-emit.so"


def _ensure_cursor_plugin(_sock_path: str) -> None:
    """Load cursor-shape-emit.so into Hyprland if not already loaded.

    Silent no-op if the .so is missing or hyprctl is unavailable.
    """
    import json, subprocess  # noqa: PLC0415
    if not _PLUGIN_SO.exists():
        _log.debug("voxy: cursor-shape-emit.so not found at %s — shape events disabled", _PLUGIN_SO)
        return
    try:
        r = subprocess.run(
            ["hyprctl", "-j", "plugin", "list"],
            capture_output=True, text=True, timeout=5,
        )
        plugins = json.loads(r.stdout) if r.returncode == 0 else []
        if any("cursor-shape-emit" in p.get("name", "") for p in plugins):
            _log.debug("voxy: cursor-shape-emit already loaded")
            return
    except Exception as exc:
        _log.debug("voxy: plugin query failed (%s)", exc)

    try:
        result = subprocess.run(
            ["hyprctl", "plugin", "load", str(_PLUGIN_SO)],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            _log.info("voxy: loaded cursor-shape-emit plugin")
        else:
            _log.warning("voxy: plugin load failed: %s", result.stderr.strip())
    except Exception as exc:
        _log.debug("voxy: hyprctl plugin load failed (%s)", exc)


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
# Xcursor helpers
# ---------------------------------------------------------------------------

def _find_xcursor_file(cursor_name: str = "default") -> Path | None:
    """Locate an xcursor file by searching standard icon theme directories."""
    theme = os.environ.get("XCURSOR_THEME", "")
    search_dirs = [
        Path.home() / ".local" / "share" / "icons",
        Path.home() / ".icons",
        Path("/usr/share/icons"),
        Path("/usr/local/share/icons"),
    ]
    themes = [theme] if theme else []
    themes += ["Adwaita", "default", "hicolor"]
    for td in search_dirs:
        for t in themes:
            if not t:
                continue
            candidate = td / t / "cursors" / cursor_name
            if candidate.exists():
                return candidate
    return None


def _parse_xcursor(path: Path, target_size: int) -> tuple[int, int, int, int, list[int]] | None:
    """Parse an Xcursor file; return (width, height, xhot, yhot, argb_pixels)."""
    import struct  # noqa: PLC0415
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if data[:4] != b"Xcur":
        return None
    ntoc = struct.unpack_from("<I", data, 12)[0]
    chunks: list[tuple[int, int]] = []
    off = 16
    for _ in range(ntoc):
        typ, subtype, pos = struct.unpack_from("<III", data, off)
        off += 12
        if typ == 0xFFFD0002:
            chunks.append((subtype, pos))
    if not chunks:
        return None
    chunks.sort(key=lambda c: abs(c[0] - target_size))
    _, pos = chunks[0]
    try:
        _, _, _, _, w, h, xhot, yhot, _ = struct.unpack_from("<IIIIIIIII", data, pos)
        pixels = list(struct.unpack_from(f"<{w * h}I", data, pos + 36))
    except struct.error:
        return None
    return w, h, xhot, yhot, pixels


def _build_cursor_outline(
    path: Path,
    target_size: int,
    color_rgb: tuple[float, float, float],
    halo: int = 2,
    scale: int = 1,
) -> tuple[Any, float, float] | None:
    """Return (cairo_surface, xhot, yhot) — a HiDPI-aware colored outline.

    Parses at target_size*scale physical pixels, sets the surface device scale
    so GTK renders it at the correct logical size without upscale blur.
    xhot/yhot are returned in logical (GTK) coordinates.
    """
    import cairo  # noqa: PLC0415

    phys_size = target_size * scale
    parsed = _parse_xcursor(path, phys_size)
    if parsed is None:
        parsed = _parse_xcursor(path, target_size)
        if parsed is None:
            return None
        scale = 1
    w, h, xhot, yhot, pixels = parsed
    r_c, g_c, b_c = (int(c * 255) for c in color_rgb)

    # Build tinted cursor surface (premultiplied ARGB32) — raw physical pixels.
    tinted = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
    buf = tinted.get_data()
    for i, p in enumerate(pixels):
        a = (p >> 24) & 0xFF
        o = i * 4
        buf[o + 0] = b_c * a // 255
        buf[o + 1] = g_c * a // 255
        buf[o + 2] = r_c * a // 255
        buf[o + 3] = a
    tinted.mark_dirty()

    # Paint halo in physical coords, punch hole, then tag the result as HiDPI.
    # All drawing on `temp` uses physical pixel coords (device_scale not yet set).
    pad = halo + 1
    tw, th = w + pad * 2, h + pad * 2
    temp = cairo.ImageSurface(cairo.FORMAT_ARGB32, tw, th)
    tc = cairo.Context(temp)
    offsets = [(ox, oy) for ox in range(-halo, halo + 1)
               for oy in range(-halo, halo + 1) if ox or oy]
    for ox, oy in offsets:
        tc.set_source_surface(tinted, pad + ox, pad + oy)
        tc.paint()
    tc.set_operator(cairo.Operator.DEST_OUT)
    tc.set_source_surface(tinted, pad, pad)
    tc.paint()

    # Mark as HiDPI so GTK renders at logical size without blur.
    temp.set_device_scale(scale, scale)

    # Hotspot in logical coordinates (GTK user-space).
    return temp, (xhot + pad) / scale, (yhot + pad) / scale


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
        self._redraw_pending = False  # idle_add coalescing flag
        # one entry per GDK monitor, filled in _on_activate.
        self._outputs: list[dict[str, Any]] = []
        self._app: Any = None
        self._ready = threading.Event()

        # Cursor outline surfaces, updated when the shape changes.
        self._cursor_size = int(os.environ.get("XCURSOR_SIZE", "24"))
        self._gdk_scale: int = 1  # set in _on_activate from first monitor
        self._cursor_shape = "default"
        self._cursor_outlines: dict[str, Any] = {}
        self._cursor_hot: tuple[float, float] = (0.0, 0.0)
        # Cache keyed by (shape_name, scale) so HiDPI changes invalidate it.
        self._shape_cache: dict[tuple[str, int], tuple[dict[str, Any], tuple[float, float]]] = {}
        self._lock = threading.Lock()

        # socket2 path for cursor shape events (plugin must be loaded).
        self._sock2_path = sock_path.replace(".socket.sock", ".socket2.sock")

        t = threading.Thread(target=self._run_gtk, daemon=True)
        t.start()
        self._ready.wait(timeout=5.0)

        # Cursor shape watcher — listens on Hyprland socket2.
        w = threading.Thread(target=self._watch_cursor_shape, daemon=True)
        w.start()

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
                if i == 0:
                    self._gdk_scale = mon.get_scale_factor()
                out = {
                    "win": None, "area": None,
                    "ox": geo.x, "oy": geo.y,
                    "bx": geo.x, "by": geo.y, "bw": geo.width, "bh": geo.height,
                    "was_active": False,
                    "linger": 0,  # frames to keep drawing after cursor leaves
                }
                self._build_window(mon, out)
                self._outputs.append(out)
            self._load_shape("default")
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
            if gx == -9999:  # position not yet known
                return
            on_this_output = (out["bx"] <= gx < out["bx"] + out["bw"]
                              and out["by"] <= gy < out["by"] + out["bh"])
            if not on_this_output and out["linger"] <= 0:
                return

            cr.set_operator(cairo.Operator.OVER)
            x, y = gx - out["ox"], gy - out["oy"]
            rgb = _COLOR_RECORDING_RGB if self._state == "recording" else _COLOR_PROCESSING_RGB

            # Cursor outline: exact xcursor shape tinted in status color.
            outline_surf = self._cursor_outlines.get(self._state)
            if outline_surf is not None:
                xhot, yhot = self._cursor_hot
                cr.set_source_surface(outline_surf, x - xhot, y - yhot)
                cr.paint()
            else:
                # Fallback: simple square contour.
                half = 16.0
                cr.set_source_rgba(*rgb, 1.0)
                cr.set_line_width(_ARROW_STROKE)
                cr.rectangle(x - half, y - half, half * 2, half * 2)
                cr.stroke()

            # Status rect anchored near cursor hotspot.
            rx = x + _RECT_OFFSET
            ry = y + _RECT_OFFSET
            if rx + _RECT_W > w:
                rx = x - _RECT_OFFSET - _RECT_W
            if ry + _RECT_H > h:
                ry = y - _RECT_OFFSET - _RECT_H
            cr.set_source_rgba(*rgb, 1.0)
            cr.set_line_width(_ARROW_STROKE)
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

    def _load_shape(self, shape_name: str) -> None:
        """Build outline surfaces for shape_name; update _cursor_outlines/_cursor_hot.

        Called from the shape-watcher thread (under _lock) and from __init__.
        Falls back to "default" if the named shape file isn't found.
        """
        with self._lock:
            scale = self._gdk_scale
            cache_key = (shape_name, scale)
            if cache_key in self._shape_cache:
                outlines, hot = self._shape_cache[cache_key]
            else:
                cursor_file = _find_xcursor_file(shape_name)
                if cursor_file is None and shape_name != "default":
                    cursor_file = _find_xcursor_file("default")
                if cursor_file is None:
                    return
                outlines: dict[str, Any] = {}
                hot: tuple[float, float] = (0.0, 0.0)
                for state, rgb in (
                    ("recording", _COLOR_RECORDING_RGB),
                    ("processing", _COLOR_PROCESSING_RGB),
                ):
                    result = _build_cursor_outline(
                        cursor_file, self._cursor_size, rgb, scale=scale
                    )
                    if result is not None:
                        surf, xhot, yhot = result
                        outlines[state] = surf
                        hot = (xhot, yhot)
                self._shape_cache[cache_key] = (outlines, hot)
            # Atomic paired update — assign hot before outlines so worst case
            # is one frame with new hot + old outlines (harmless offset), not crash.
            self._cursor_hot = hot
            self._cursor_outlines = outlines
            self._cursor_shape = shape_name

    def _watch_cursor_shape(self) -> None:
        """Listen on Hyprland socket2 for cursorshape>> events.

        Reconnects automatically if the socket drops. Calls _load_shape() on
        each new shape, then schedules a GTK redraw via idle_add.
        If socket2 is not available (plugin not loaded) the thread exits quietly.
        """
        if not self._sock2_path:
            _log.debug("voxy: socket2 path unknown — cursor shape detection disabled")
            return
        import subprocess  # noqa: PLC0415
        while True:
            try:
                s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                s.connect(self._sock2_path)
                # Ask plugin to re-emit current shape so we get initial state.
                try:
                    subprocess.run(
                        ["hyprctl", "dispatch", "cursorshapequery"],
                        capture_output=True, timeout=2,
                    )
                except Exception:
                    pass
                buf = ""
                while True:
                    chunk = s.recv(4096).decode("utf-8", "replace")
                    if not chunk:
                        break
                    buf += chunk
                    if "\n" not in buf:
                        continue
                    # Drain all complete lines, coalescing cursormove events
                    # to the latest position — never queue stale frames.
                    lines, _, buf = buf.rpartition("\n")
                    latest_move: tuple[int, int] | None = None
                    new_shape: str | None = None
                    for line in lines.split("\n"):
                        if line.startswith("cursormove>>"):
                            if not self._visible:
                                continue
                            try:
                                xs, ys = line[len("cursormove>>"):].split(",", 1)
                                latest_move = (int(xs), int(ys))
                            except ValueError:
                                continue
                        elif line.startswith("cursorshape>>"):
                            shape = line[len("cursorshape>>"):].strip()
                            if shape and shape != self._cursor_shape:
                                new_shape = shape
                    if new_shape is not None:
                        self._load_shape(new_shape)
                    if latest_move is not None and latest_move != self._cursor_xy:
                        self._cursor_xy = latest_move
                        if not self._redraw_pending:
                            self._redraw_pending = True
                            try:
                                self._GLib.idle_add(
                                    self._redraw_and_clear,
                                    priority=self._GLib.PRIORITY_HIGH,
                                )
                            except Exception:
                                self._redraw_pending = False
                    elif new_shape is not None:
                        try:
                            self._GLib.idle_add(self._redraw_all)
                        except Exception:
                            pass
                s.close()
            except OSError as exc:
                _log.debug("voxy: socket2 disconnected (%s), reconnecting", exc)
            except Exception as exc:
                _log.debug("voxy: shape watcher error (%s)", exc)
            time.sleep(1.0)

    def _redraw_all(self) -> None:
        for out in self._outputs:
            area = out.get("area")
            if area is not None:
                area.queue_draw()

    def _redraw_and_clear(self) -> bool:
        self._redraw_pending = False
        self._redraw_all()
        return False

    def show(self) -> None:
        def do() -> bool:
            self._state = "recording"
            self._visible = True
            # Seed cursor pos on first show — cursormove only fires on motion.
            if self._cursor_xy[0] == -9999:
                pos = _hyprland_cursorpos(self._sock_path)
                if pos is not None:
                    self._cursor_xy = pos
            self._redraw_all()
            return False
        self._GLib.idle_add(do)

    def processing(self) -> None:
        def do() -> bool:
            self._state = "processing"
            self._redraw_all()
            return False
        self._GLib.idle_add(do)

    def hide(self) -> None:
        def do() -> bool:
            self._visible = False
            self._redraw_all()
            return False
        self._GLib.idle_add(do)

    def stop(self) -> None:
        def do() -> bool:
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
        _ensure_cursor_plugin(sock_path)
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
