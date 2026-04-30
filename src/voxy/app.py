"""App — hotkey-driven record/transcribe/insert loop."""

from __future__ import annotations

import threading

from .audio import AudioRecorder, AudioFeedback
from .hotkey import HotkeyListener, check_input_group
from .inserter import TextInserter
from .overlay import OverlayUI
from .postprocess import PostProcessor
from .transcriber import Transcriber


class App:
    """Push-to-talk: hold hotkey to record, release to transcribe and insert."""

    _recorder: AudioRecorder
    _transcriber: Transcriber
    _inserter: TextInserter
    _postprocessor: PostProcessor
    _overlay: OverlayUI
    _feedback: AudioFeedback
    _key: str

    def __init__(
        self,
        recorder: AudioRecorder,
        transcriber: Transcriber,
        inserter: TextInserter,
        postprocessor: PostProcessor,
        overlay: OverlayUI,
        feedback: AudioFeedback,
        key: str = "right_alt",
    ) -> None:
        self._recorder = recorder
        self._transcriber = transcriber
        self._inserter = inserter
        self._postprocessor = postprocessor
        self._overlay = overlay
        self._feedback = feedback
        self._key = key

    def run(self) -> None:
        """Block until Ctrl-C, firing record/transcribe/insert on each press."""
        check_input_group()
        listener = HotkeyListener(
            key=self._key,
            on_press=self._on_press,
            on_release=self._on_release,
        )
        listener.start()
        print("voxy — hold hotkey to dictate. Ctrl-C to quit.")
        done = threading.Event()
        try:
            if self._overlay._root:
                self._overlay.wait_loop()
            else:
                done.wait()
        except KeyboardInterrupt:
            pass
        finally:
            listener.stop()

    def _on_press(self) -> None:
        self._overlay.show()
        self._feedback.play_start()
        self._recorder.start()

    def _on_release(self) -> None:
        audio = self._recorder.stop()
        self._overlay.processing()
        self._feedback.play_stop()
        text = self._transcriber.transcribe(audio)
        text = self._postprocessor.process(text)
        self._inserter.insert(text)
        self._overlay.hide()
