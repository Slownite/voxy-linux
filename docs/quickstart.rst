Quickstart
==========

Three steps to your first transcript.

1. Install
----------

.. tab-set::

   .. tab-item:: uvx (try without installing)

      .. code-block:: bash

         uvx voxy-linux

   .. tab-item:: pipx (persistent)

      .. code-block:: bash

         pipx install voxy-linux

   .. tab-item:: Arch / Manjaro (AUR)

      .. code-block:: bash

         yay -S voxy-linux

   .. tab-item:: NixOS

      Add the flake module to your config — see :doc:`installation`.

2. Install the system dependencies
----------------------------------

voxy uses native tools for audio capture and text insertion. Install the
set that matches your distro **and** your display server.

**Audio (required):**

.. list-table::
   :header-rows: 1
   :widths: 20 80

   * - Distro
     - Command
   * - Arch
     - ``sudo pacman -S portaudio``
   * - Debian / Ubuntu
     - ``sudo apt install libportaudio2``
   * - Fedora
     - ``sudo dnf install portaudio``
   * - NixOS
     - add ``pkgs.portaudio`` to ``environment.systemPackages``
       (or ``nix-shell -p portaudio`` for ad-hoc)

**Text insertion — Wayland:**

.. list-table::
   :header-rows: 1
   :widths: 20 80

   * - Distro
     - Command
   * - Arch
     - ``sudo pacman -S wl-clipboard ydotool`` then ``systemctl --user enable --now ydotool``
   * - Debian / Ubuntu
     - ``sudo apt install wl-clipboard ydotool`` then ``systemctl --user enable --now ydotool``
   * - Fedora
     - ``sudo dnf install wl-clipboard ydotool`` then ``systemctl --user enable --now ydotool``
   * - NixOS
     - ``programs.ydotool.enable = true;`` plus ``pkgs.wl-clipboard``

**Text insertion — X11:**

.. list-table::
   :header-rows: 1
   :widths: 20 80

   * - Distro
     - Command
   * - Arch
     - ``sudo pacman -S xclip xdotool``
   * - Debian / Ubuntu
     - ``sudo apt install xclip xdotool``
   * - Fedora
     - ``sudo dnf install xclip xdotool``
   * - NixOS
     - add ``pkgs.xclip pkgs.xdotool`` to ``environment.systemPackages``

3. Start dictating
------------------

.. code-block:: bash

   voxy

The first run opens a small prompt to pick a Whisper model size. Default
is ``auto``: ``small`` (~244 MB) on GPU or recent CPU, ``base`` (~74 MB)
or ``tiny`` (~39 MB) on older CPUs. The model is downloaded once into
``~/.cache/voxy/models/`` with a progress bar; subsequent runs reuse
the cache.

Then:

#. Open any text input — editor, browser, chat, IDE.
#. Hold **Right Alt** (the default hotkey).
#. Speak.
#. Release.

Text appears in the window within a second or two. A small overlay shows
**REC** while you speak and **PROCESSING** while it transcribes.

That's it. See :doc:`usage` for indicators, tray icon, and tips.
