# ADR-0001: Cursor-anchored recording overlay

- Status: **Proposed**
- Date: 2026-05-03
- Deciders: @dphov
- Tags: ui, wayland, x11, hyprland

## Context and Problem Statement

Voxy currently shows recording state in a fixed corner overlay
([overlay.py](https://github.com/samanddima/voxy-linux/blob/main/src/voxy/overlay.py)).
The user requested an
indicator anchored to the mouse cursor — a green frame around the
cursor plus a small status rectangle to its bottom-right — visible only
while the PTT hotkey is held and during the subsequent transcription.

The challenge is that the two display servers Voxy targets (X11 and
Wayland) expose pointer position and global overlay surfaces in
fundamentally different ways, and the chosen approach must also work on
Hyprland specifically (the primary deployment target).

How should we render and position a cursor-anchored overlay across X11,
generic Wayland, and Hyprland?

## Decision Drivers

- Must follow the cursor smoothly on both display servers.
- Must not consume mouse or keyboard input (click-through).
- Must coexist with the existing Tk-based corner overlay.
- Hyprland (Wayland) is the primary target; pure-X11 must keep working.
- Keep dependency footprint reasonable; opt-in via config.
- Avoid 60 Hz subprocess polling (CPU cost).

## Considered Options

1. **Per-server native surfaces**: Tk override-redirect on X11; GTK4 +
   `gtk4-layer-shell` on Wayland with Hyprland IPC for cursor position.
2. **Single fullscreen Tk window** with X11 SHAPE extension for
   click-through and per-pixel alpha for transparency.
3. **Cursor-theme swap** — change the system cursor while recording
   (`hyprctl setcursor` on Hyprland, XFixes on X11). No overlay
   windows; loses the status rectangle.
4. **`hyprctl notify` anchored near cursor** — zero new dependencies;
   no border, no real follow-cursor, no click-through guarantees.
5. **Reuse existing corner overlay** — drop the cursor-anchored
   requirement; iterate on the corner widget instead.

## Decision Outcome

**Chosen: Option 1 — per-server native surfaces.**

It is the only option that delivers the requested visual (frame +
status rect, both following the cursor, with click-through) on both X11
and Hyprland, with acceptable CPU cost.

The implementation lives in a new `src/voxy/cursor_overlay.py` behind a
`CursorOverlay` protocol with three back-ends:

- `_X11CursorOverlay` — Tk override-redirect windows + `pynput.mouse.Listener` + `python-xlib` SHAPE for click-through.
- `_WaylandCursorOverlay` — GTK4 + `gtk4-layer-shell` single fullscreen layer surface, drawn with Cairo, cursor position polled at 60 Hz over Hyprland's IPC socket (raw socket, not `hyprctl` subprocess).
- `_NullCursorOverlay` — no-op fallback for non-Hyprland Wayland or missing optional deps.

A factory `build_cursor_overlay(config)` selects the back-end based on
`WAYLAND_DISPLAY`, `HYPRLAND_INSTANCE_SIGNATURE`, and import success.
Default `[ui] cursor_overlay = false`; opt-in.

### Positive consequences

- Smooth follow-cursor on both targets.
- True click-through (XShape empty input region / Wayland empty input region).
- One process; Tk on the main thread, GTK4 main loop on a worker thread.
- Cursor position via Hyprland IPC socket → ~0.6 % CPU at 60 Hz.

### Negative consequences

- Adds ~50 MB of system dependencies on Wayland hosts that opt in
  (`gtk4`, `gtk4-layer-shell`, `python-gobject`, `python-cairo`).
- Three implementations to maintain.
- Two GUI toolkits (Tk + GTK4) in one process — non-trivial interplay.
- Multi-monitor support deferred to a follow-up ADR.
- Other Wayland compositors (Sway, KDE, GNOME) get the no-op until
  someone adds a per-compositor cursor-position source.

## Pros and Cons of the Other Options

### Option 2: Single fullscreen Tk + SHAPE

- ➕ Single window, no jitter.
- ➕ One toolkit.
- ➖ X11 SHAPE handles input region but not per-pixel alpha; that
  requires an RGBA visual under a compositor — fragile with
  `overrideredirect`.
- ➖ Does not work on native Wayland at all.

### Option 3: Cursor-theme swap

- ➕ Zero new windows; trivial to implement; works on both servers.
- ➕ No click-through problem (it's a cursor, not a window).
- ➖ Loses the status rectangle entirely.
- ➖ Requires a custom cursor-theme asset shipped with Voxy.
- Kept on the shelf as a graceful-fallback if Option 1 dependencies
  prove unacceptable.

### Option 4: `hyprctl notify` near cursor

- ➕ Zero new dependencies on Hyprland.
- ➖ Hyprland-only; no X11 story.
- ➖ Notification anchor is approximate; no real follow.
- ➖ Cannot draw a border around the cursor.

### Option 5: Reuse corner overlay

- ➕ No new code.
- ➖ Does not satisfy the request.

## Implementation Plan

When greenlit:

1. `CursorOverlay` protocol + `_NullCursorOverlay` + factory + config
   field. Wire into `App` as a no-op.
2. X11 back-end: 5 Tk windows (4 strips + status rect), pynput hook,
   60 Hz throttle.
3. Wayland (Hyprland) back-end: GTK4 + `gtk4-layer-shell`, Cairo draw,
   raw Hyprland-socket cursor poll.
4. Click-through: XShape on X11, empty input region on Wayland.
5. Edge-flip logic so the status rect never clips a screen edge.
6. `presetup-arch.sh` adds the four system packages; `pyproject.toml`
   gains a `cursor-overlay` extra.
7. Tests: factory selection, null-path no-op behavior.

## Open Questions

1. Color / stroke / size: hard-coded constants or `[ui]` fields?
2. Show overlay during processing as well as recording? (Current plan: yes.)
3. Multi-monitor: ship v1 single-monitor, or block on multi-monitor?
4. If GTK4 dependency is rejected, do we accept Option 3
   (cursor-theme swap) as a degraded Wayland path?

## Update 2026-05-11 — outline moved into the Hyprland plugin

The original Wayland back-end drew both the cursor outline and the status
badge from a GTK4 layer-shell surface, fed by `cursormove>>` IPC events from
the `cursor-shape-emit` plugin. On fast cursor sweeps the outline visibly
trailed Hyprland's hardware cursor plane — the chain of kernel → Hyprland →
EventManager → socket2 → Python thread → `GLib.idle_add` → GTK frame clock →
`wl_surface.commit` → vblank can never beat the HW cursor plane.

The cursor outline now lives inside `cursor-shape-emit` itself
([hyprland-plugin/cursor-shape-emit/main.cpp](../../hyprland-plugin/cursor-shape-emit/main.cpp)).
A `render` callback draws the four contour strips with
`g_pHyprOpenGL->renderRect` during `RENDER_LAST_MOMENT`, sharing the
compositor's cursor frame. Three new dispatchers
(`voxy:overlay_show / _processing / _hide`) toggle plugin state from Python.
The Python side stopped consuming `cursormove>>` and now only owns the small
status badge, polling `cursorpos` over the Hyprland socket at ~30 Hz — the
badge's 26 px offset hides the residual lag.

## References

- Existing corner overlay: [src/voxy/overlay.py](../../src/voxy/overlay.py)
- App lifecycle hooks where show/hide will be called: [src/voxy/app.py](../../src/voxy/app.py)
- `gtk4-layer-shell`: https://github.com/wmww/gtk4-layer-shell
- Hyprland IPC: https://wiki.hyprland.org/IPC/
- MADR template: https://adr.github.io/madr/
