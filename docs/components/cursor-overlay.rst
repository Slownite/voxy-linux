cursor_overlay.py
=================

Cursor-anchored outline. Mirrors the same recording / processing state as
the corner overlay, but draws *around* the mouse cursor instead of in a
fixed corner.

Source: ``src/voxy/cursor_overlay.py``.

See :doc:`../decisions/0001-cursor-overlay` for the choice of approach.

Backends
--------

- **X11**: single fullscreen Tk window with the X11 SHAPE extension
  punching a transparent hole everywhere except a small rectangle around
  the cursor. Per-frame XQueryPointer polling at ~60 Hz.
- **Wayland (generic)**: GTK4 + ``gtk4-layer-shell`` overlay, one window
  per monitor. Cursor position pulled via Hyprland's
  ``hyprctl cursorpos`` (Wayland has no generic pointer-position API).
- **Hyprland (preferred)**: defers all drawing to the
  ``cursor-shape-emit`` C++ plugin. See :doc:`../hyprland-plugin/index`.
  Python only handles the on/off dispatcher calls and the small status
  badge to the cursor's bottom-right.

Why three backends?
-------------------

The same problem looks different on each server:

1. X11 lets us punch a per-pixel transparent hole and use XFixes + XInput
   to read cursor position cheaply. Tk + SHAPE covers it.
2. Generic Wayland has no fullscreen-overlay primitive without
   ``wlr-layer-shell``. GTK4 ``layer-shell`` covers most modern Wayland
   compositors but still costs one compositor frame of latency.
3. Hyprland's render pass is hookable from a C++ plugin, so we can draw
   the outline inside the same frame as the cursor — *zero* perceived
   lag.

The Python module auto-detects the environment at startup and picks the
appropriate backend.
