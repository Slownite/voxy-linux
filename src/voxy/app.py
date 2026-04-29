"""App — temporary Enter-triggered record/transcribe loop (issue #3)."""

from __future__ import annotations

from .audio import AudioRecorder
from .transcriber import Transcriber


class App:
    """Minimal record → transcribe → print loop for pipeline validation.

    Press Enter to start recording, Enter again to stop.
    Replaced by hotkey-driven loop in issue #5.
    """

    _recorder: AudioRecorder
    _transcriber: Transcriber

    def __init__(self, recorder: AudioRecorder, transcriber: Transcriber) -> None:
        self._recorder = recorder
        self._transcriber = transcriber

    def run(self) -> None:
        """Block until KeyboardInterrupt, looping record/transcribe."""
        print("voxy — Enter to start, Enter again to stop. Ctrl-C to quit.")
        try:
            while True:
                input("[ press Enter to start recording ]")
                self._recorder.start()
                input("[ recording… press Enter to stop ]")
                audio = self._recorder.stop()
                text = self._transcriber.transcribe(audio)
                print(f"transcript: {text!r}")
        except KeyboardInterrupt:
            pass
