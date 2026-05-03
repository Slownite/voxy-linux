"""App — hotkey-driven record/transcribe/insert loop."""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

from .audio import AudioRecorder, AudioFeedback
from .hotkey import HotkeyListener, check_input_group
from .inserter import TextInserter, check_tools
from .overlay import OverlayUI
from .postprocess import PostProcessor
from .transcriber import Transcriber

if TYPE_CHECKING:
    from .tray import TrayIcon


class App:
    """Push-to-talk: hold hotkey to record, release to transcribe and insert."""

    _recorder: AudioRecorder
    _transcriber: Transcriber
    _inserter: TextInserter
    _postprocessor: PostProcessor
    _overlay: OverlayUI
    _feedback: AudioFeedback
    _key: str
    _tray: TrayIcon | None
    _done: threading.Event

    def __init__(
        self,
        recorder: AudioRecorder,
        transcriber: Transcriber,
        inserter: TextInserter,
        postprocessor: PostProcessor,
        overlay: OverlayUI,
        feedback: AudioFeedback,
        key: str = "right_alt",
        tray: TrayIcon | None = None,
    ) -> None:
        self._recorder = recorder
        self._transcriber = transcriber
        self._inserter = inserter
        self._postprocessor = postprocessor
        self._overlay = overlay
        self._feedback = feedback
        self._key = key
        self._tray = tray
        self._done = threading.Event()

    def stop(self) -> None:
        """Request graceful shutdown of the run loop."""
        self._done.set()
        root = self._overlay._root
        if root is not None:
            try:
                root.after(0, root.destroy)
            except Exception:
                pass

    def run(self) -> None:
        """Block until Ctrl-C, firing record/transcribe/insert on each press."""
        check_input_group()
        check_tools(self._inserter._method)
        listener = HotkeyListener(
            key=self._key,
            on_press=self._on_press,
            on_release=self._on_release,
        )
        listener.start()
        if self._tray:
            self._tray.start()
            self._tray.set_state("idle")
        device = self._transcriber._ct2_device.upper()
        print(f"voxy — hold hotkey to dictate. Ctrl-C to quit. [{device}]")
        try:
            if self._overlay._root:
                self._overlay.wait_loop()
            else:
                self._done.wait()
        except KeyboardInterrupt:
            pass
        finally:
            listener.stop()
            if self._tray:
                self._tray.stop()

    def _on_press(self) -> None:
        self._overlay.show()
        self._feedback.play_start()
        self._recorder.start()
        if self._tray:
            self._tray.set_state("recording")
        print("voxy: recording…", flush=True)

    def _on_release(self) -> None:
        audio = self._recorder.stop()
        self._overlay.processing()
        self._feedback.play_stop()
        if self._tray:
            self._tray.set_state("processing")
        print("voxy: processing…", flush=True)

        def _pipeline() -> None:
            try:
                text = self._transcriber.transcribe(audio)
                text = self._postprocessor.process(text)
                if text:
                    print(f"voxy: {text}", flush=True)
                else:
                    print("voxy: (no speech detected)", flush=True)
                self._inserter.insert(text)
            except Exception as e:
                print(f"voxy error: {e}", flush=True)
            finally:
                self._overlay.hide()
                if self._tray:
                    self._tray.set_state("idle")

        threading.Thread(target=_pipeline, daemon=True).start()
