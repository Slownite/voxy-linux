# cursor-shape-emit

Hyprland plugin that draws voxy's recording-state outline around the cursor
directly inside the compositor, and emits cursor-shape change events over
Hyprland's IPC socket.

> **Why in-compositor?** A separate Wayland client surface always trails the
> HW-cursor plane by ≥1 compositor frame plus IPC hop. Drawing inside
> Hyprland's render pass shares the same frame as the cursor and avoids the
> trail entirely.

---

## Layout

```
cursor-shape-emit/
├── outline.hpp / outline.cpp   # pure halo-outline pixel builder (cairo only)
├── main.cpp                    # Hyprland plugin glue, hooks, dispatchers
├── Makefile                    # build / test / install
├── justfile                    # task wrapper (`just <recipe>`)
└── tests/
    ├── test_outline.cpp        # unit tests (cairo only, no Hyprland)
    ├── integration_smoke.sh    # live-Hyprland smoke test
    └── golden/arrow_green.png  # checked-in golden image fixture
```

Splitting `outline.{hpp,cpp}` out of `main.cpp` lets the test binary link
against the pixel builder without pulling Hyprland headers (which need a GL
context).

---

## Build

```sh
just build        # or: make
just install      # writes to ~/.local/share/hyprland/plugins/
just reload       # install + hyprctl plugin reload
```

Requires `g++` with C++26, Hyprland dev headers, cairo, hyprcursor,
hyprutils, libdrm.

The plugin links against Hyprland's installed headers — if your Hyprland was
built from a different tag, rebuild the plugin from source.

---

## Public surface

Dispatchers (`hyprctl dispatch …`):

| Name | Effect |
|---|---|
| `cursorshapequery` | re-emit the current cursor shape as `cursorshape>>name` IPC event |
| `voxy:overlay_show` | show outline, recording colour (green) |
| `voxy:overlay_processing` | show outline, processing colour (orange) |
| `voxy:overlay_hide` | hide outline |

IPC event (on `socket2.sock`):

```
cursorshape>>left_ptr
cursorshape>>text
cursorshape>>pointer
```

Fires every time `CCursorManager::setCursorFromName` is called with a new
name. Subscribe via the existing Hyprland IPC pattern (e.g. `socat -u
UNIX-CONNECT:$XDG_RUNTIME_DIR/hypr/$HYPRLAND_INSTANCE_SIGNATURE/.socket2.sock -`).

---

## How it draws

1. The plugin listens for the `Event::bus()->m_events.render.stage` signal
   and reacts at the `RENDER_LAST_MOMENT` stage.
2. It pulls the current cursor buffer from
   `g_pPointerManager->currentCursorImage()`, reads its ARGB pixels via
   `IBuffer::beginDataPtr()`, and builds a coloured halo outline with cairo:
   paint the tinted source at every (2·HALO+1)² offset, then `DEST_OUT` the
   silhouette to leave only the antialiased outline ring.
3. The outline is uploaded as a `CTexture` and queued as a
   `CTexPassElement` on `g_pHyprRenderer->m_renderPass`. Hyprland's
   `endRender()` flushes `m_renderPass.render()` immediately after the
   `RENDER_LAST_MOMENT` emit (see upstream `src/render/Renderer.cpp`), so
   our outline lands in the same frame as the cursor.

Both states (recording / processing) are built once per cursor buffer
swap and cached. A sticky `s_lastGoodOutlines` keeps the previous outline
visible if the current buffer briefly becomes unreadable (e.g. a client
sets a `wl_surface` cursor during a drag).

---

## Tests

```sh
just test           # unit tests (cairo only, ~ms)
just test-asan      # unit tests with ASAN + UBSan
just smoke          # integration test against live Hyprland
just smoke-lint     # shellcheck the smoke script
just check          # everything above
just regen-golden   # refresh the golden PNG fixture
```

Unit tests cover:
- Padding dimensions
- Silhouette punch-out (`DEST_OUT`)
- Halo ring shape (Chebyshev distance ≤ HALO)
- Colour tint (green/orange/mixed)
- Premultiplied invariant (channel ≤ alpha, exact values within ±2)
- Mid-alpha source pixels (anti-aliased input)
- Symmetry across both axes
- Source row stride > `sw*4` (no padding leak)
- Rectangular silhouette (multi-pixel)
- Golden PNG fixture compare (tolerance: ≤2 LSBs per channel, ≤1 % divergent pixels)

The smoke test only runs when `HYPRLAND_INSTANCE_SIGNATURE` is set. It
loads the plugin, exercises every dispatcher, optionally verifies the
`cursorshape>>` IPC event via `socat`, then unloads — restoring the prior
plugin state with a `trap cleanup EXIT`.

CI (`.github/workflows/hyprland-plugin-tests.yml`) runs the unit + ASAN +
shellcheck pipeline on every push that touches the plugin.

---

## Hooks (and why they're brittle)

We hook two internal Hyprland functions via `HyprlandAPI::createFunctionHook`:

| Function | Reason |
|---|---|
| `CCursorManager::setCursorFromName(const std::string&)` | emit `cursorshape>>name` IPC events |
| `CInputManager::onMouseMoved(IPointer::SMotionEvent)` | schedule framebuffer damage around the cursor every motion so the renderer keeps producing frames while the overlay is up |

Targets are resolved by `findFunctionsByName` + a demangled-signature suffix
match (`findUniqueOverload` in `main.cpp`). On a Hyprland upgrade that
renames or re-signs these, the plugin loads but emits a notification:

> *voxy: cursor-shape-emit could not hook setCursorFromName — cursorshape IPC events disabled*

The outline path itself does **not** depend on the hooks; it reads
`g_pPointerManager` state directly.

---

## Updating for a new Hyprland release

When you upgrade Hyprland:

1. `just build` — if it compiles, the API surfaces we use are intact.
2. `just smoke` — if all dispatchers return `ok` and IPC fires, runtime is fine.
3. If the outline stops appearing: verify in upstream
   `src/render/Renderer.cpp` that `RENDER_LAST_MOMENT` is still emitted
   **before** `endRender()` calls `m_renderPass.render()`. That ordering is
   the contract we depend on.
4. If hooks log warnings: re-check the demangled name suffixes in
   `findUniqueOverload` calls in `main.cpp`.

---

## Caveats

- Texture upload via `CTexture` ctor uses `glTexImage2D` synchronously, so
  the source pixel buffer can be freed immediately after construction.
  Keep this in mind if you swap to async upload — the cairo surface would
  need a longer lifetime.
- The plugin assumes `CCursorBuffer` (Hyprland's own cursor buffer) is
  `DRM_FORMAT_ARGB8888`. Client-set `wl_surface` cursors with dmabuf
  backing fall through the sticky outline path — that's working as
  intended, not a bug.
- Animated cursors trigger a full outline rebuild on every animation
  frame (buffer pointer swap invalidates the cache). Acceptable for the
  current shape set but flagged in code review as a future throttle target.

---

## Versioning

Plugin version string is in the `PLUGIN_INIT` return value in `main.cpp`.
Bump it whenever you ship a behaviour change.
