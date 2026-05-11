Privacy
=======

voxy is local-first. The following statements are facts about the
default configuration, verifiable from the code.

What stays on your machine
--------------------------

- **Audio**: captured into RAM, transcribed locally, then discarded.
  Never written to disk.
- **Transcripts**: written to the system clipboard, pasted into the
  focused window, then forgotten. voxy keeps no history.
- **Models**: the Whisper model is downloaded **once** from Hugging
  Face on first use into ``~/.cache/voxy/models/``. After that, no
  further network requests for inference.

What leaves your machine
------------------------

Nothing.

There is no cloud backend, no telemetry, no update check, no LLM
post-processing pass that talks to the network. The post-processing
pass (:doc:`components/postprocess`) is a small **rule-based**
transformer — punctuation commands, auto-capitalisation, filler
stripping — entirely local.

System integration
------------------

voxy reads the microphone, listens for one global hotkey, writes to the
clipboard, and synthesises one paste keystroke. It does not:

- Watch keyboard or mouse activity outside of its single hotkey.
- Read clipboard contents (only writes).
- Talk to any system service other than your audio stack, your D-Bus
  notification daemon, your D-Bus tray host, and (on Hyprland) the
  compositor's IPC socket for cursor position.

Logs
----

Run voxy in the foreground to see live logs. Logs include transcript
text — useful when diagnosing accuracy issues. If you want quieter
logs, set ``logging.level = "warning"`` in ``config.toml``.
