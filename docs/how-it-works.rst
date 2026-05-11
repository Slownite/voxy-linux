How it works
============

A plain-English tour of what happens between hotkey press and pasted
text.

The pipeline
------------

.. mermaid::

    flowchart LR
        HK[Hotkey pressed] --> REC[Capture audio]
        REC --> WHISPER[Local Whisper model]
        WHISPER --> CLEAN[Optional cleanup]
        CLEAN --> PASTE[Paste into focused window]

Step by step:

1. **Hotkey pressed.** voxy already had the microphone open, so there's
   no warm-up delay. It just starts saving the incoming audio.
2. **You speak.** Audio frames accumulate in memory while the key is
   held.
3. **Hotkey released.** voxy stops recording and hands the audio to a
   local copy of OpenAI Whisper (via the ``faster-whisper`` backend,
   which runs the same model 2–4× faster).
4. **Whisper transcribes.** Typically 0.4–1.5 s on a recent CPU for a
   5-second utterance. Slower for bigger models, faster for smaller
   ones.
5. **Optional cleanup.** If you've enabled post-processing, a small
   local LLM tidies up punctuation, fillers, capitalisation.
6. **Paste.** voxy writes the result to your system clipboard and
   simulates a paste keystroke into whatever window is focused.

Why local?
----------

Every step runs on your machine. The audio never goes to a server. The
transcription model lives in ``~/.cache/voxy/`` and stays there. Your
clipboard, your input, your data.

Latency floor
-------------

Three things matter for "time from releasing the key to seeing text":

.. list-table::
   :header-rows: 1
   :widths: 50 50

   * - Stage
     - What you can do about it
   * - Whisper inference
     - Pick a smaller model. ``tiny`` is near-instant; ``small`` is the
       sweet spot.
   * - LLM cleanup (if enabled)
     - Run a smaller cleanup model locally, or turn cleanup off.
   * - Paste keystroke
     - Nothing — it's how the OS works. ~30 ms.

A typical full round-trip on a modern CPU with ``small`` Whisper and
cleanup disabled is around **1 second** for a short utterance — varies
with utterance length, CPU generation, and chosen model.

The cursor outline
------------------

If you're on **Hyprland**, voxy ships a tiny compositor plugin that
draws the recording-state outline *inside* the compositor's own render
loop. That means the outline updates in the same frame as the cursor —
there's no perceived lag, even when you whip the mouse around.

On other compositors voxy uses a layer-shell Wayland surface, which
adds one frame (~16 ms) of follow lag. On X11 it uses the SHAPE
extension to punch a transparent hole in a Tk window and polls cursor
position. All three back-ends look identical to the user.
