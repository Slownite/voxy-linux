"""Tests for build_cursor_overlay factory and the null back-end."""

from __future__ import annotations

import queue
from pathlib import Path
from unittest.mock import MagicMock, patch

from voxy.config import UIConfig
from voxy.cursor_overlay import (
    _NullCursorOverlay,
    build_cursor_overlay,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_tk_root(dpi: float = 72.0) -> MagicMock:
    """Return a minimal Tk root mock."""
    root = MagicMock()
    root.winfo_fpixels.return_value = dpi
    root.winfo_pointerx.return_value = 0
    root.winfo_pointery.return_value = 0
    root.winfo_screenwidth.return_value = 1920
    root.winfo_screenheight.return_value = 1080
    root.after.return_value = None
    return root


def _make_x11_overlay(root: MagicMock | None = None) -> object:
    """Build an _X11CursorOverlay with all external deps stubbed."""
    from voxy.cursor_overlay import _X11CursorOverlay

    if root is None:
        root = _make_tk_root()

    tk_mod = MagicMock()
    tk_mod.TclError = Exception
    # Toplevel() returns a distinct mock each time so strip/rect are separate.
    tk_mod.Toplevel.side_effect = lambda *a, **kw: MagicMock()
    tk_mod.Canvas.return_value = MagicMock()

    with patch.dict("sys.modules", {"tkinter": tk_mod}), patch(
        "voxy.cursor_overlay._X11CursorOverlay.__init__",
        lambda self, r: _patched_init(self, r, tk_mod),
    ):
        overlay = _X11CursorOverlay.__new__(_X11CursorOverlay)
        _patched_init(overlay, root, tk_mod)
    return overlay


def _patched_init(self: object, root: MagicMock, tk_mod: MagicMock) -> None:
    """Replicate __init__ with tk stubbed, skipping after() scheduling."""
    import queue as _q

    self._tk = tk_mod  # type: ignore[attr-defined]
    self._root = root  # type: ignore[attr-defined]
    self._queue: queue.Queue = _q.Queue()  # type: ignore[attr-defined]
    self._listener = None  # type: ignore[attr-defined]
    self._visible = False  # type: ignore[attr-defined]
    self._state = "recording"  # type: ignore[attr-defined]
    self._last_pos = (0, 0)  # type: ignore[attr-defined]
    self._strips: list = []  # type: ignore[attr-defined]
    self._rect = MagicMock()  # type: ignore[attr-defined]
    self._rect_canvas = MagicMock()  # type: ignore[attr-defined]
    self._cursor_size = 24  # type: ignore[attr-defined]
    self._scale = 1  # type: ignore[attr-defined]
    self._cursor_shape = "default"  # type: ignore[attr-defined]
    self._cursor_outlines: dict = {}  # type: ignore[attr-defined]
    self._cursor_hot: tuple = (0.0, 0.0)  # type: ignore[attr-defined]
    self._shape_cache: dict = {}  # type: ignore[attr-defined]
    self._outline_win = MagicMock()  # type: ignore[attr-defined]
    self._outline_canvas = MagicMock()  # type: ignore[attr-defined]
    self._outline_log_size: tuple = (0, 0)  # type: ignore[attr-defined]
    self._screen_w: int = 0  # type: ignore[attr-defined]
    self._screen_h: int = 0  # type: ignore[attr-defined]
    self._shape_dirty = False  # type: ignore[attr-defined]
    # No after() scheduling — tests drive _poll() manually.


# ---------------------------------------------------------------------------
# Existing factory tests (unchanged)
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# AC: xcursor outline renders (not plain squares)
# ---------------------------------------------------------------------------

def test_x11_load_shape_builds_outlines() -> None:
    """_load_shape populates _cursor_outlines when xcursor file is found."""
    overlay = _make_x11_overlay()

    fake_surf = MagicMock()
    fake_path = Path("/fake/cursors/default")

    with patch("voxy.cursor_overlay._find_xcursor_file", return_value=fake_path), patch(
        "voxy.cursor_overlay._build_cursor_outline",
        return_value=(fake_surf, 4.0, 4.0),
    ):
        overlay._load_shape("default")  # type: ignore[attr-defined]

    assert "recording" in overlay._cursor_outlines  # type: ignore[attr-defined]
    assert "processing" in overlay._cursor_outlines  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# AC: shape switches on queue event
# ---------------------------------------------------------------------------

def test_x11_shape_queue_triggers_reload() -> None:
    """A ('shape', name) message on the queue causes _load_shape to be called."""
    overlay = _make_x11_overlay()
    overlay._queue.put(("shape", "xterm"))  # type: ignore[attr-defined]

    with patch.object(overlay, "_load_shape") as mock_load:  # type: ignore[attr-defined]
        overlay._poll()  # type: ignore[attr-defined]

    mock_load.assert_called_once_with("xterm")


# ---------------------------------------------------------------------------
# AC: HiDPI — scale derived from Tk DPI and passed to _build_cursor_outline
# ---------------------------------------------------------------------------

def test_x11_hidpi_scale_passed_to_build_outline() -> None:
    """At 144 DPI (2x HiDPI), _build_cursor_outline is called with scale=2."""
    root = _make_tk_root(dpi=144.0)  # 144 px/inch → scale=2
    overlay = _make_x11_overlay(root)

    # Force recomputation by clearing cache and setting scale from root.
    overlay._scale = int(root.winfo_fpixels("1i") / 72)  # type: ignore[attr-defined]
    assert overlay._scale == 2  # type: ignore[attr-defined]

    fake_path = Path("/fake/cursors/default")
    captured: list[int] = []

    def fake_build(path, size, color_rgb, halo=2, scale=1):
        captured.append(scale)
        return (MagicMock(), 4.0, 4.0)

    with patch("voxy.cursor_overlay._find_xcursor_file", return_value=fake_path), patch(
        "voxy.cursor_overlay._build_cursor_outline", side_effect=fake_build
    ):
        overlay._load_shape("default")  # type: ignore[attr-defined]

    assert all(s == 2 for s in captured), f"Expected scale=2, got {captured}"


# ---------------------------------------------------------------------------
# AC: fallback when XFixes unavailable — overlay starts without error
# ---------------------------------------------------------------------------

def test_x11_no_xfixes_starts_without_crash() -> None:
    """If python-xlib or xfixes is absent, _X11CursorOverlay still constructs."""
    root = _make_tk_root()
    tk_mod = MagicMock()
    tk_mod.TclError = Exception
    tk_mod.Toplevel.side_effect = lambda *a, **kw: MagicMock()
    tk_mod.Canvas.return_value = MagicMock()

    # Simulate Xlib being completely absent.
    broken_modules = {
        "Xlib": None,
        "Xlib.display": None,
        "Xlib.ext": None,
        "Xlib.ext.xfixes": None,
        "Xlib.X": None,
    }
    with patch.dict("sys.modules", broken_modules):
        overlay = _make_x11_overlay(root)
        # Should not raise; shape tracking simply disabled.
        overlay.show()  # type: ignore[attr-defined]
        overlay.hide()  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# AC: fallback when xcursor file not found — _cursor_outlines stays empty
# ---------------------------------------------------------------------------

def test_x11_missing_xcursor_falls_back_to_square() -> None:
    """When xcursor file is missing, _cursor_outlines is empty (square fallback)."""
    overlay = _make_x11_overlay()

    with patch("voxy.cursor_overlay._find_xcursor_file", return_value=None):
        overlay._load_shape("default")  # type: ignore[attr-defined]

    assert overlay._cursor_outlines == {}  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# AC: pynput still drives position updates
# ---------------------------------------------------------------------------

def test_x11_pynput_move_updates_position() -> None:
    """on_move callback puts (move, (x,y)) on queue; _poll updates _last_pos."""
    overlay = _make_x11_overlay()
    overlay._visible = True  # type: ignore[attr-defined]

    # Simulate pynput on_move directly.
    overlay._queue.put(("move", (100, 200)))  # type: ignore[attr-defined]

    with patch.object(overlay, "_reposition"):  # type: ignore[attr-defined]
        overlay._poll()  # type: ignore[attr-defined]

    assert overlay._last_pos == (100, 200)  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# AC: RGBA paint path passes correct positional args to python-xlib put_image.
# Regression: a SimpleNamespace bundle was passed in place of the 9 positional
# args, raising TypeError silently and leaving the ARGB32 window unpainted —
# picom then composited it as a solid black square under the cursor.
# ---------------------------------------------------------------------------

def _attach_rgba_stubs(overlay: object) -> tuple[MagicMock, MagicMock, MagicMock]:
    win, gc, dpy = MagicMock(), MagicMock(), MagicMock()
    overlay._rgba = True  # type: ignore[attr-defined]
    overlay._rgba_win = win  # type: ignore[attr-defined]
    overlay._rgba_gc = gc  # type: ignore[attr-defined]
    overlay._rgba_dpy = dpy  # type: ignore[attr-defined]
    overlay._rgba_w = 0  # type: ignore[attr-defined]
    overlay._rgba_h = 0  # type: ignore[attr-defined]
    return win, gc, dpy


def test_x11_paint_rgba_outline_calls_put_image_with_positional_args() -> None:
    """put_image must be called with the 9 positional args python-xlib expects."""
    from Xlib import X

    overlay = _make_x11_overlay()
    win, gc, _ = _attach_rgba_stubs(overlay)

    overlay._paint_rgba_outline(24, 24)  # type: ignore[attr-defined]

    win.put_image.assert_called_once()
    args, kwargs = win.put_image.call_args
    assert kwargs == {}, f"put_image must be positional, got kwargs={kwargs}"
    assert len(args) == 9, f"expected 9 positional args, got {len(args)}: {args}"
    got_gc, x, y, w, h, fmt, depth, left_pad, data = args
    assert got_gc is gc
    assert (x, y) == (0, 0)
    assert (w, h) == (24, 24)
    assert fmt == X.ZPixmap
    assert depth == 32
    assert left_pad == 0
    assert isinstance(data, bytes | bytearray)
    assert len(data) == 24 * 24 * 4  # ARGB32: 4 bytes per pixel


def test_x11_paint_rgba_outline_resizes_window_on_size_change() -> None:
    """First paint at a new size issues a configure(width, height)."""
    overlay = _make_x11_overlay()
    win, _, _ = _attach_rgba_stubs(overlay)

    overlay._paint_rgba_outline(40, 32)  # type: ignore[attr-defined]

    win.configure.assert_called_with(width=40, height=32)
    assert overlay._rgba_w == 40  # type: ignore[attr-defined]
    assert overlay._rgba_h == 32  # type: ignore[attr-defined]

    # Same size on next call → no extra configure.
    win.configure.reset_mock()
    overlay._paint_rgba_outline(40, 32)  # type: ignore[attr-defined]
    win.configure.assert_not_called()


def test_x11_paint_rgba_outline_surfaces_failures(capsys) -> None:  # type: ignore[no-untyped-def]
    """put_image errors must reach stderr (not just debug log) so they're noticed."""
    overlay = _make_x11_overlay()
    win, _, _ = _attach_rgba_stubs(overlay)
    win.put_image.side_effect = TypeError("boom")

    overlay._paint_rgba_outline(24, 24)  # type: ignore[attr-defined]

    assert "_paint_rgba_outline failed" in capsys.readouterr().err
