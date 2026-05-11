Troubleshooting
===============

Common issues and how to fix them.

"Nothing happens when I press the hotkey"
-----------------------------------------

.. dropdown:: On Wayland — is ``ydotool`` running?

   voxy listens for the hotkey through ``ydotool``'s socket on Wayland.

   .. code-block:: bash

      systemctl --user status ydotool       # active?
      systemctl --user enable --now ydotool

.. dropdown:: Is another process grabbing the key?

   Some keyboards' on-board software (e.g. Razer / Logitech daemons)
   intercept modifier keys system-wide. Try a different hotkey in
   ``config.toml``:

   .. code-block:: toml

      [hotkey]
      key = "Super_R"          # or F12, etc.

.. dropdown:: Is voxy actually running?

   If you're using the systemd service:

   .. code-block:: bash

      voxy --daemon status

   Otherwise, just start it in the foreground:

   .. code-block:: bash

      voxy                       # foreground; Ctrl+C to stop

"Audio is empty / silent"
-------------------------

.. dropdown:: Is the right microphone selected?

   .. code-block:: bash

      python -m sounddevice          # list devices

   Put the device name in ``config.toml``:

   .. code-block:: toml

      [audio]
      device = "Yeti Stereo Microphone"

.. dropdown:: Is the microphone muted at the OS level?

   ``wpctl status`` (PipeWire) or ``pavucontrol`` (PulseAudio) —
   confirm the default source isn't muted and has reasonable volume.

"Text appears slowly"
---------------------

Most likely: Whisper model is too big for your CPU. Lower it:

.. code-block:: toml

   [transcriber]
   model = "small"      # or "base", or "tiny"

Or, if you have an NVIDIA GPU:

.. code-block:: toml

   [transcriber]
   device       = "cuda"
   compute_type = "float16"

"The cursor outline doesn't follow the cursor"
----------------------------------------------

.. dropdown:: Are you on Hyprland?

   The zero-lag outline needs the ``cursor-shape-emit`` plugin loaded:

   .. code-block:: bash

      hyprctl plugin list | grep cursor-shape-emit

   If missing, see the
   :doc:`Hyprland plugin docs <hyprland-plugin/index>` for installation.

.. dropdown:: On other Wayland compositors

   Cursor position polling uses Hyprland-specific IPC. On generic
   Wayland the outline uses a layer-shell surface that lags one
   compositor frame. There is no way to do better without compositor
   cooperation.

"voxy crashed / I see a Python traceback"
-----------------------------------------

Run voxy in the foreground and capture the trace:

.. code-block:: bash

   voxy 2>&1 | tee /tmp/voxy.log

Then `open an issue <https://github.com/samanddima/voxy-linux/issues>`_
with the log attached. Include:

- Distro + version
- Display server (``echo $XDG_SESSION_TYPE``)
- Compositor (``echo $XDG_CURRENT_DESKTOP`` or ``hyprctl version``)
- Output of ``voxy --version``

Getting more help
-----------------

- **Issues**: https://github.com/samanddima/voxy-linux/issues
- **Discussions**: https://github.com/samanddima/voxy-linux/discussions
