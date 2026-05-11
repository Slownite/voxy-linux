Recording pipeline
==================

State machine
-------------

The daemon is a tight three-state loop driven by hotkey transitions:

.. mermaid::

    stateDiagram-v2
        [*] --> Idle
        Idle --> Recording: hotkey press
        Recording --> Transcribing: hotkey release
        Transcribing --> Idle: text inserted

``Idle``
    Audio device is open, stream gated off, overlay hidden, cursor-outline
    plugin in ``_hide`` state.

``Recording``
    PortAudio gate opens. Frames append to an in-memory ring buffer.
    Overlay shows **REC**, cursor outline turns green via
    ``voxy:overlay_show``.

``Transcribing``
    Buffer is closed and fed to ``faster-whisper``. Overlay flips to
    **PROCESSING**, cursor outline switches to orange via
    ``voxy:overlay_processing``. When the model returns, optional LLM
    post-processing runs, then the inserter writes the text and dispatches
    a synthetic paste. On completion the daemon goes back to ``Idle`` and
    issues ``voxy:overlay_hide``.

Latency budget
--------------

End-to-end latency (release → text in window) on a recent laptop CPU,
``small`` Whisper model, ~5 s utterance:

.. list-table::
   :header-rows: 1
   :widths: 30 20 50

   * - Stage
     - Typical
     - Notes
   * - Audio finalisation
     - < 5 ms
     - Closing the ring, framing into a numpy array.
   * - Whisper inference
     - 0.4–1.5 s
     - Dominates. Use a smaller model for snappier feedback.
   * - LLM post-process
     - 0 / 80–400 ms
     - Optional; off by default. Skip if not configured.
   * - Clipboard write
     - < 5 ms
     - xclip / wl-copy via subprocess.
   * - Synthetic paste
     - 20–80 ms
     - xdotool / ydotool keystroke + receiving app's paste handler.

The audio path is *not* on the critical latency path during recording —
playback of the start/stop chime (``start.wav`` / ``stop.wav``) hides the
small amount of overhead.

Threading model
---------------

One asyncio loop owns the daemon. The audio callback runs on PortAudio's
own thread and pushes frames into a thread-safe queue, draining into the
loop via ``loop.call_soon_threadsafe``. ``faster-whisper`` inference
blocks; it runs in ``asyncio.to_thread`` so the loop stays responsive
(hotkey release while transcribing is detected immediately and queues a
cancel).
