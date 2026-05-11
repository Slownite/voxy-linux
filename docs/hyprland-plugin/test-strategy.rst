Test strategy
=============

The plugin runs inside Hyprland, so traditional unit testing is hard
(no GL context, no compositor, no live ``g_pPointerManager``). We split
the code so that the pure-pixel work lives in its own translation unit
linkable against a host-side test binary, and the Hyprland-glue path is
covered by a live smoke test.

Layers
------

.. list-table::
   :header-rows: 1
   :widths: 22 28 50

   * - Layer
     - Command
     - Covers
   * - **Unit**
     - ``just test``
     - Pure pixel builder (``outline.cpp``): geometry, halo ring, tint,
       premultiplied invariant, anti-aliased input, stride handling,
       golden PNG compare.
   * - **Sanitizers**
     - ``just test-asan``
     - Same suite under AddressSanitizer + UBSan. Catches OOB, leaks,
       UB at near-zero extra cost.
   * - **Smoke**
     - ``just smoke``
     - Loads the built ``.so`` into the running Hyprland; exercises every
       dispatcher; subscribes to ``socket2.sock`` and verifies the
       ``cursorshape>>`` IPC event; unloads on exit via ``trap``.
   * - **Lint**
     - ``just smoke-lint``
     - ``shellcheck`` over the smoke script.
   * - **CI**
     - ``.github/workflows/hyprland-plugin-tests.yml``
     - Runs unit + ASAN + shellcheck on every push that touches the
       plugin.

Golden fixture
--------------

Unit tests include a checked-in PNG fixture
(``tests/golden/arrow_green.png``) generated from a synthetic arrow
silhouette. The compare uses two tolerances simultaneously:

- Per-channel diff ≤ 2 LSBs.
- ≤ 1 % of pixels diverge.

Cairo on the same machine is byte-exact in practice; the tolerance
absorbs across-distro variance without masking real regressions.

Add ``just regen-golden`` when you intentionally change the outline
algorithm.
