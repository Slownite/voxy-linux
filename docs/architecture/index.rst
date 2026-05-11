Architecture
============

How voxy is put together internally. This section is for curious users
and people considering contributing.

System overview
---------------

voxy is a single-process Python daemon. It captures audio while you hold
a global hotkey, transcribes it locally via ``faster-whisper``,
optionally applies LLM post-processing, then inserts the result into the
focused window using a display-server-appropriate clipboard + synthetic
paste.

.. mermaid::

    flowchart LR
        subgraph Input
            HK[Global hotkey]
            MIC[Microphone]
        end
        subgraph Daemon
            APP[app.py event loop]
            AUDIO[audio.py recorder]
            TR[transcriber.py<br/>faster-whisper]
            PP[postprocess.py<br/>optional LLM]
            INS[inserter.py<br/>clipboard + synthetic paste]
        end
        subgraph UI
            OV[overlay.py<br/>corner status]
            CUR[cursor_overlay.py<br/>cursor-anchored]
            TRAY[tray.py SNI]
        end
        subgraph Compositor
            PLUG[hyprland-plugin<br/>in-compositor outline]
        end

        HK --> APP
        MIC --> AUDIO --> APP
        APP --> TR --> PP --> INS
        APP --> OV
        APP --> CUR --> PLUG
        APP --> TRAY

Module map
----------

.. list-table::
   :header-rows: 1
   :widths: 18 82

   * - Module
     - Responsibility
   * - ``app.py``
     - Daemon entry point, state machine, lifecycle of every other module.
   * - ``audio.py``
     - PortAudio capture loop, ring buffer, push-to-talk gate.
   * - ``hotkey.py``
     - Global hotkey listener (X11 keymap or ``ydotool``/evdev on Wayland).
   * - ``transcriber.py``
     - ``faster-whisper`` model load, CTranslate2 inference, language detection.
   * - ``postprocess.py``
     - Optional LLM cleanup pass (punctuation, capitalisation, fillers).
   * - ``inserter.py``
     - Clipboard write + synthetic paste keystroke (X11: xclip+xdotool;
       Wayland: wl-clipboard+ydotool).
   * - ``overlay.py``
     - Fixed-corner Tk recording-state indicator.
   * - ``cursor_overlay.py``
     - Cursor-anchored outline. Per-server backend: X11 native; Wayland via
       GTK4 + ``gtk4-layer-shell``; Hyprland via the in-compositor plugin
       under ``hyprland-plugin/cursor-shape-emit/``.
   * - ``tray.py``
     - StatusNotifierItem (D-Bus) integration via ``dbus-next``.
   * - ``daemon.py``
     - systemd user-service manager: ``voxy --daemon {install,remove,status}``.
   * - ``config.py``
     - TOML config loader + defaults; see :doc:`../configuration`.

.. toctree::
   :hidden:

   pipeline
   display-servers
