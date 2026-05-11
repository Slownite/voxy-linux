tray.py
=======

StatusNotifierItem implementation via ``dbus-next``. Mirrors the three
recording states with distinct icons, plus a right-click menu with
**Quit**.

Source: ``src/voxy/tray.py``.

Compatibility
-------------

Works wherever an SNI host runs:

- **waybar** (default Hyprland setup)
- **KDE Plasma**
- **GNOME** with the AppIndicator extension
- **i3 / sway** with ``swaync`` or another SNI watcher

No fallback to legacy ``XEmbed`` / Xlib system trays — those are dead
elsewhere; we don't reinvent them.

Icon set
--------

Three SVG icons live in ``src/voxy/icons/``. They are loaded once at
daemon start and held in memory; dbus serves the relative file path via
the SNI ``IconName`` property.
