Usage
=====

The workflow
------------

1. **Hold** the hotkey (default: **Right Alt**).
2. **Speak**.
3. **Release**.

Your transcribed words appear in the focused window.

A short audible chime plays on press and release so you don't have to
look at the screen to know recording started and stopped.

Indicators
----------

While voxy is recording or transcribing, three optional indicators
mirror its state:

.. list-table::
   :header-rows: 1
   :widths: 25 25 50

   * - Indicator
     - Where
     - What you see
   * - Corner overlay
     - Screen corner (configurable)
     - **REC** (red) while recording → **PROCESSING** (amber) while
       transcribing → hidden when done.
   * - Cursor outline
     - Anchored to the mouse cursor
     - A coloured outline around the actual cursor shape, matching the
       same three states.
   * - Tray icon
     - Status bar (waybar, KDE, GNOME)
     - Identical state via SNI; right-click for **Quit**.

You can disable any of them in :doc:`configuration`. They are all
purely optional — voxy still works headlessly.

Toasts
------

By default a small desktop notification (via your notification daemon —
``mako``, ``dunst``, KDE, GNOME Shell) tells you when a transcript has
landed in your clipboard. Useful on multi-monitor setups when the
overlay is on a different screen than where you're looking.

Running modes
-------------

Two ways to run voxy:

**Foreground.** Run it directly in a terminal:

.. code-block:: bash

   voxy

Useful for debugging — you see live logs. Stop with ``Ctrl+C``.

**Systemd user service.** Set up once, runs on every login:

.. code-block:: bash

   voxy --daemon install        # enable and start the service
   voxy --daemon status         # check it
   voxy --daemon remove         # disable and uninstall

Service logs land in ``journalctl --user -u voxy.service``.

Tips
----

- **Long dictations**: voxy caps a single utterance at 30 s (configurable).
  Past that the recording stops automatically; release the key and the
  partial text is still transcribed.
- **Accuracy**: bigger Whisper models = better transcription, slower
  inference. ``small`` is the sweet spot for most laptops; bump to
  ``medium`` if you have a GPU.
- **Other languages**: ``transcriber.language = "auto"`` lets Whisper
  detect on every utterance. Pin to a specific ISO code (e.g. ``"en"``,
  ``"de"``, ``"ru"``) if you only ever dictate in one language —
  detection takes a small fraction of a second per utterance.
- **Punctuation / fillers**: enable the optional :doc:`post-processing
  pass <components/postprocess>` to clean transcripts via a local LLM
  before they hit the clipboard.
