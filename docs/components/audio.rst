audio.py
========

PortAudio capture loop via ``sounddevice``. Opens a single input stream
at daemon start and keeps it open for the lifetime of the process —
opening on every hotkey press introduces ~100 ms of warm-up latency on
most distros.

Source: ``src/voxy/audio.py``.

Design notes
------------

- **Always-open stream.** Avoids ALSA/PulseAudio device-claim races
  observed when toggling input streams quickly.
- **Gate, don't open/close.** A boolean flag controls whether incoming
  callback frames are appended to the buffer. The PortAudio thread keeps
  running regardless.
- **Sample rate fixed at 16 kHz, mono, float32.** Matches what Whisper
  expects natively — no resampling in our path.
- **Default input device.** voxy reads ``sounddevice``'s default input
  device. To switch, set the system default in PipeWire / PulseAudio.

``AudioFeedback``
-----------------

Same module exposes ``AudioFeedback``, which plays
``start.wav`` / ``stop.wav`` chimes on hotkey press / release when
``ui.audio_feedback = true``. The chimes are loaded once at startup and
played from RAM. Off by default — visual indicators usually suffice.

Extension points
----------------

If you need a different backend (e.g. raw ALSA, pipewire native), swap
``sounddevice.RawInputStream`` with your own producer that posts numpy
``float32`` mono 16 kHz frames into the same queue.
