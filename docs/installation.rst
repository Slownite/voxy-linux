Installation
============

Pick the path that matches your setup.

uvx — try it without installing
-------------------------------

.. code-block:: bash

   uvx voxy-linux

`uv <https://docs.astral.sh/uv/>`_ downloads and runs voxy in an
isolated venv. Fast for a one-off try.

pipx — persistent isolated install
----------------------------------

.. code-block:: bash

   pipx install voxy-linux
   voxy

AUR — Arch / Manjaro
--------------------

.. code-block:: bash

   yay -S voxy-linux            # or paru, etc.

The PKGBUILD pulls in all system dependencies.

NixOS — flake module
--------------------

Add to your ``flake.nix``:

.. code-block:: nix

   {
     inputs.voxy.url = "github:samanddima/voxy-linux";

     outputs = { self, nixpkgs, voxy, ... }: {
       nixosConfigurations.<host> = nixpkgs.lib.nixosSystem {
         modules = [
           voxy.nixosModules.voxy
           {
             services.voxy.enable = true;
             users.users.<your-user>.extraGroups = [ "input" ];
           }
         ];
       };
     };
   }

The module enables ``ydotool``, installs voxy, and provides options:

.. list-table::
   :header-rows: 1
   :widths: 30 15 15 40

   * - Option
     - Type
     - Default
     - Description
   * - ``services.voxy.enable``
     - ``bool``
     - ``false``
     - Enable voxy.
   * - ``services.voxy.hotkey``
     - ``string``
     - ``"right_alt"``
     - Push-to-talk key (evdev / pynput name).
   * - ``services.voxy.modelSize``
     - ``enum``
     - ``"small"``
     - Whisper model size.
   * - ``services.voxy.overlayCorner``
     - ``enum``
     - ``"bottom-right"``
     - Recording overlay corner.

The module generates a ``config.toml`` from these declared options and
passes it via the ``VOXY_CONFIG`` environment variable.

From source
-----------

.. code-block:: bash

   git clone https://github.com/samanddima/voxy-linux
   cd voxy-linux
   just setup
   uv run voxy

See :doc:`contributing` for the local development loop and tests.

System dependencies
-------------------

Regardless of install method, voxy needs the following native tools.

Audio (required)
~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 22 78

   * - Distro
     - Command
   * - Arch / Manjaro
     - ``sudo pacman -S portaudio``
   * - Debian / Ubuntu
     - ``sudo apt install libportaudio2``
   * - Fedora
     - ``sudo dnf install portaudio``
   * - NixOS
     - add ``pkgs.portaudio`` to ``environment.systemPackages``,
       or ``nix-shell -p portaudio`` for an ad-hoc shell

Text insertion — Wayland
~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 22 78

   * - Distro
     - Command
   * - Arch / Manjaro
     - ``sudo pacman -S wl-clipboard ydotool`` ·
       ``systemctl --user enable --now ydotool``
   * - Debian / Ubuntu
     - ``sudo apt install wl-clipboard ydotool`` ·
       ``systemctl --user enable --now ydotool``
   * - Fedora
     - ``sudo dnf install wl-clipboard ydotool`` ·
       ``systemctl --user enable --now ydotool``
   * - NixOS
     - ``programs.ydotool.enable = true;`` plus ``pkgs.wl-clipboard``
       in ``environment.systemPackages``

Text insertion — X11
~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 22 78

   * - Distro
     - Command
   * - Arch / Manjaro
     - ``sudo pacman -S xclip xdotool``
   * - Debian / Ubuntu
     - ``sudo apt install xclip xdotool``
   * - Fedora
     - ``sudo dnf install xclip xdotool``
   * - NixOS
     - add ``pkgs.xclip pkgs.xdotool`` to ``environment.systemPackages``

Optional: Hyprland plugin
~~~~~~~~~~~~~~~~~~~~~~~~~

If you're on Hyprland, the in-compositor plugin gives a zero-lag cursor
outline. The AUR package and NixOS module install it automatically. If
you installed via ``uvx`` / ``pipx`` / ``pip``, install it manually —
see the :doc:`Hyprland plugin docs <hyprland-plugin/index>`.

Platform support
----------------

- **Linux only.** voxy targets X11, generic Wayland, and Hyprland.
- **Python ≥ 3.11.**
- **GPU optional.** CPU works fine for ``small`` and ``base`` Whisper
  models; CUDA accelerates ``medium`` / ``large-v3`` significantly.
