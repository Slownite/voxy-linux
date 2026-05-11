overlay.py
==========

Fixed-corner recording status indicator. Three visual states: hidden,
**REC** (red), **PROCESSING** (amber).

Source: ``src/voxy/overlay.py``.

Backends
--------

- **X11**: Tk window with ``override-redirect = True``, anchored to a
  user-configured screen corner. The corner is recomputed on every show
  so multi-monitor / DPI changes are handled.
- **Wayland**: GTK4 window pinned to the anchor edge via
  ``gtk4-layer-shell``. ``set_keyboard_mode(NONE)`` keeps it
  click-through.

Both backends share the same state-machine protocol — ``show_recording``,
``show_processing``, ``hide`` — so the rest of the daemon doesn't care
which one is active.

Configuration
-------------

In ``config.toml``:

.. code-block:: toml

   [ui]
   overlay        = true                # set to false to disable
   overlay_corner = "bottom-right"      # top-left | top-right | bottom-left | bottom-right

The tray icon still mirrors the state when ``overlay = false``.
