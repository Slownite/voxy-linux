Configuration
=============

voxy reads ``~/.config/voxy/config.toml``. The file is created on first
run with sensible defaults — edit it any time, then restart voxy
(``voxy --daemon remove && voxy --daemon install`` if you use the
service, otherwise stop the foreground process and start it again).

Every option below has a working default; the whole file is optional.

Override the config path with the ``VOXY_CONFIG`` environment variable.
``VOXY_CONFIG`` takes precedence over ``~/.config/voxy/config.toml``.

Schema
------

The full schema, with defaults shown:

.. code-block:: toml

   # ~/.config/voxy/config.toml

   [hotkey]
   key = "right_alt"              # evdev / pynput key name

   [model]
   size     = "auto"              # auto | tiny[.en] | base[.en] | small[.en]
                                  #      | medium[.en] | large-v1 | large-v2 | large-v3
   language = "auto"              # auto-detect, or a BCP-47 code (en, de, ru, …)
   device   = "auto"              # auto | cpu | cuda

   [insertion]
   method = "auto"                # auto | x11 | wayland

   [post_processing]
   punctuation_commands = true    # apply [post_processing.substitutions]
   auto_capitalize      = true
   strip_fillers        = false
   fillers              = ["uh", "um", "hmm"]

   [post_processing.substitutions]
   "new line"      = "\n"
   "new paragraph" = "\n\n"
   "comma"         = ","
   "period"        = "."

   [ui]
   overlay        = true               # corner REC/PROCESSING badge
   overlay_corner = "bottom-right"     # top-left | top-right | bottom-left | bottom-right
   audio_feedback = false              # play start.wav / stop.wav chimes
   notify         = true               # desktop toast on transcript landing
   tray           = true               # status-notifier-item tray icon
   cursor_overlay = true               # outline anchored to the mouse cursor

   [logging]
   level = "info"                 # debug | info | warning | error

Sections
--------

``[hotkey]``
~~~~~~~~~~~~

``key`` — the push-to-talk key in evdev/pynput style (lowercased,
modifier suffix). Examples: ``right_alt``, ``right_ctrl``, ``super_r``,
``f12``. Voxy listens on press *and* release.

``[model]``
~~~~~~~~~~~

``size`` — Whisper model. Bigger = more accurate, slower. ``auto`` picks
based on CPU flags (AVX / VNNI) and core count, or ``small`` on GPU.
The ``.en`` variants are English-only and noticeably faster for
English-only dictation.

``language`` — ``"auto"`` detects per utterance; pin to a BCP-47 code
(``"en"``, ``"de"``, …) to skip detection. The
``model.fallback_language`` field present in some older configs is no
longer read.

``device`` — GPU selection.

- ``auto`` — use GPU if found, fall back silently to CPU.
- ``cuda`` — require GPU; warn and fall back to CPU if none is present.
- ``cpu`` — always CPU regardless of hardware.

On GPU the compute type is selected automatically
(``int8_float16`` on Turing+, ``float16`` on Pascal+,
``float32`` fallback).

``[insertion]``
~~~~~~~~~~~~~~~

``method = "auto"`` — picks ``x11`` or ``wayland`` based on
``XDG_SESSION_TYPE`` / ``WAYLAND_DISPLAY``. Override only if
auto-detection is wrong.

When the focused window is a known terminal emulator (alacritty, kitty,
ghostty, gnome-terminal, konsole, …), voxy automatically substitutes
``Ctrl+Shift+V`` for ``Ctrl+V`` so the paste lands inside the terminal
rather than triggering a shortcut.

``[post_processing]``
~~~~~~~~~~~~~~~~~~~~~

A small **rule-based** pass between transcription and insertion. No
LLM. All operations are local and cheap.

- ``punctuation_commands`` — applies the ``substitutions`` table to
  the transcript so you can say "comma" and get ``,``.
- ``auto_capitalize`` — capitalises the first letter of every
  sentence.
- ``strip_fillers`` — removes the strings in ``fillers`` (case-insensitive,
  whole-word). Off by default; Whisper is already quite good at not
  transcribing fillers verbatim.
- ``substitutions`` — phrase → replacement table. Keys are matched
  case-insensitively as whole phrases. Strings may contain ``\n`` for
  newlines.

``[ui]``
~~~~~~~~

- ``overlay`` — fixed-corner ``REC`` / ``PROCESSING`` badge.
- ``overlay_corner`` — which screen corner.
- ``audio_feedback`` — play ``start.wav`` on press and ``stop.wav``
  on release.
- ``notify`` — desktop notification on transcript landing.
- ``tray`` — StatusNotifierItem tray icon mirroring overlay state.
- ``cursor_overlay`` — outline anchored to the mouse cursor (see
  :doc:`components/cursor-overlay`).

On Wayland, when the cursor outline is active, the corner overlay is
suppressed to avoid showing the same state twice.

``[logging]``
~~~~~~~~~~~~~

``level`` — Python logging level. ``debug`` is useful when filing bug
reports.

How values are resolved
-----------------------

Defaults live in code (``src/voxy/config.py``). Your file's values
override them field by field. An invalid value raises ``ConfigError``
with a clear message at startup; an unknown key is ignored.

Hot reload
----------

Not supported. Changes take effect on next start.
