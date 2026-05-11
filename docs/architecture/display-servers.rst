Display-server matrix
=====================

voxy targets three Linux display-server environments. Each has its own
hotkey backend, clipboard tool, paste keystroke synthesiser, and overlay
implementation.

.. list-table::
   :header-rows: 1
   :widths: 18 27 27 28

   * -
     - X11
     - Wayland (generic)
     - Hyprland
   * - Hotkey
     - ``Xlib`` keymap grab
     - ``evdev`` via ``ydotool``
     - ``evdev`` via ``ydotool``
   * - Clipboard
     - ``xclip``
     - ``wl-clipboard``
     - ``wl-clipboard``
   * - Paste keystroke
     - ``xdotool key ctrl+v``
     - ``ydotool key ctrl+v``
     - ``ydotool key ctrl+v``
   * - Corner overlay
     - Tk override-redirect
     - GTK4 + ``gtk4-layer-shell``
     - GTK4 + ``gtk4-layer-shell``
   * - Cursor outline
     - Tk fullscreen + SHAPE
     - GTK4 layer-shell overlay
     - **In-compositor plugin** (see :doc:`../hyprland-plugin/index`)
   * - Tray
     - StatusNotifierItem (D-Bus)
     - StatusNotifierItem (D-Bus)
     - StatusNotifierItem (D-Bus)

Why a Hyprland plugin
---------------------

The cursor-shape outline is the only feature that needs sub-frame latency.
Wayland clients receive pointer events through the compositor's input
graph, so any client-side surface that "follows the cursor" will trail
Hyprland's hardware cursor plane by at least one compositor frame plus the
IPC hop.

To eliminate that trail we ship a tiny Hyprland plugin that draws the
outline inside the renderer's own pass on the ``RENDER_LAST_MOMENT``
signal — the outline ends up in the *same frame* as the cursor. See
:doc:`../hyprland-plugin/index` for the full design.
