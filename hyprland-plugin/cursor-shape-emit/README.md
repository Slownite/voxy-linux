# cursor-shape-emit

Hyprland plugin that re-emits cursor shape and position changes as
Hyprland IPC events so voxy's cursor overlay can mirror the live system
cursor shape (I-beam, hand, resize, …) while recording.

## Events

| Event | Payload | When |
|---|---|---|
| `cursorshape>>name` | xcursor name (`default`, `text`, `pointer`, `nesw-resize`, …) | Hyprland calls `CCursorManager::setCursorFromName` |
| `cursormove>>x,y` | global cursor coords | Hyprland calls `CInputManager::onMouseMoved` |

A `hyprctl dispatch cursorshapequery` is also registered so a freshly
connected client can re-request the current shape.

## When voxy uses it

The plugin is **optional**. voxy only consults it when:

- you're on Hyprland (Wayland), AND
- `[ui] cursor_overlay = true` in `~/.config/voxy/config.toml`.

Without the plugin the overlay still draws a green frame around the
pointer; with the plugin it additionally outlines whichever cursor
shape Hyprland is currently rendering.

On every startup voxy runs `_ensure_cursor_plugin()`
([`src/voxy/cursor_overlay.py`](../../src/voxy/cursor_overlay.py)) which:

1. Checks for `~/.local/share/hyprland/plugins/cursor-shape-emit.so`.
2. If present, queries `hyprctl plugin list` and runs
   `hyprctl plugin load <path>` when not already loaded.
3. If absent, logs a debug line and continues — no error.

Nothing in the Python install path (pip, pipx, uvx, AUR) builds or
installs this `.so`. You build it yourself, once, against your running
Hyprland's headers.

> **NixOS:** the Nix flake doesn't build this plugin and `hyprctl
> plugin load` against a hand-built `.so` isn't the right workflow on
> NixOS. Use Hyprland's own plugin support
> ([wiki.hyprland.org/Plugins/Using-Plugins](https://wiki.hyprland.org/Plugins/Using-Plugins/))
> to package and load this directory.

## Build & install

Requires the repo checked out and Hyprland's development headers
(e.g. `pacman -S hyprland`). The plugin must be rebuilt whenever
Hyprland is upgraded — its ABI is not stable across versions.

```bash
make           # produces cursor-shape-emit.so
make install   # copies to ~/.local/share/hyprland/plugins/
```

Then restart voxy (`systemctl --user restart voxy` if running as a
user service) and verify with:

```bash
hyprctl plugin list   # cursor-shape-emit should appear
```

## Uninstall

```bash
hyprctl plugin unload ~/.local/share/hyprland/plugins/cursor-shape-emit.so
rm ~/.local/share/hyprland/plugins/cursor-shape-emit.so
```
