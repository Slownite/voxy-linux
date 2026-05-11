hotkey.py
=========

Global push-to-talk hotkey listener. Reads key state via ``pynput`` and
``evdev`` depending on the display server.

Source: ``src/voxy/hotkey.py``.

Why not compositor binds?
-------------------------

Hyprland-native ``bind = …`` keybinds fire on press but cannot easily
signal release; PTT semantics need both. Going through evdev/pynput
gives us press *and* release with the same code path on both display
servers.

Configuration
-------------

The hotkey is parsed from ``config.toml``:

.. code-block:: toml

   [hotkey]
   key = "right_alt"

Names follow the lowercase modifier-suffix style used by pynput / evdev:

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Name
     - Key
   * - ``right_alt``
     - default; the right-side Alt key
   * - ``right_ctrl``
     - right-side Control
   * - ``super_r``
     - right Super (Windows / Cmd) key
   * - ``f12``
     - function key F12

If a name fails to resolve at startup, voxy raises ``ConfigError`` with
the list of valid names — pick another and restart.
