inserter.py
===========

Writes transcribed text into the focused window via clipboard + a
synthetic paste keystroke. The "paste it" approach beats key-by-key
synthesis on three axes:

- **Speed** — one keystroke, regardless of transcript length.
- **Unicode** — clipboard handles any character; synthetic keystrokes
  trip on layouts and dead keys.
- **Undo** — receiving app gets a single undo step.

Source: ``src/voxy/inserter.py``.

Implementation
--------------

.. code-block:: text

   X11      → xclip -selection clipboard           → xdotool key ctrl+v
   Wayland  → wl-copy                              → ydotool key 29+47:1 ...

Terminal-aware paste
--------------------

Most terminal emulators bind ``Ctrl+V`` to the literal ``^V`` character
and require ``Ctrl+Shift+V`` for paste. voxy detects the focused window
and substitutes automatically when the class matches one of:

- ``alacritty``
- ``kitty``
- ``ghostty``
- ``gnome-terminal``
- ``konsole``
- ``foot``
- ``wezterm``

No configuration needed — the detection is by Wayland focus class
(``hyprctl activewindow`` on Hyprland, ``swaymsg`` on Sway,
``gdbus``-based on GNOME Wayland) or ``xdotool`` on X11.

Configuration
-------------

``[insertion] method = "auto"`` decides X11 vs Wayland based on
``XDG_SESSION_TYPE`` / ``WAYLAND_DISPLAY``. Override only if
auto-detection is wrong.

Failure mode
------------

If the required CLI tools are missing, the inserter logs a one-line
hint at startup pointing at the install command for the user's distro
and disables itself. The rest of voxy keeps running so the user can
still hear the chime and see the overlay, just without paste.
