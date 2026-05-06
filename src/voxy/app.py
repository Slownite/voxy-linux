"""App — hotkey-driven record/transcribe/insert loop."""

from __future__ import annotations

import signal
import threading
from typing import TYPE_CHECKING

from .audio import AudioRecorder, AudioFeedback
from .cursor_overlay import CursorOverlay, _NullCursorOverlay
from .hotkey import HotkeyListener, check_input_group
from .inserter import TextInserter, check_tools
from .overlay import OverlayUI
from .postprocess import PostProcessor
from .transcriber import Transcriber

if TYPE_CHECKING:
    from .config import ConfigLoader
    from .tray import TrayIcon


class App:
    """Push-to-talk: hold hotkey to record, release to transcribe and insert."""

    _recorder: AudioRecorder
    _transcriber: Transcriber
    _inserter: TextInserter
    _postprocessor: PostProcessor
    _overlay: OverlayUI
    _cursor_overlay: CursorOverlay
    _feedback: AudioFeedback
    _key: str
    _tray: TrayIcon | None
    _done: threading.Event
    _config_loader: ConfigLoader | None
    _device_setting: str
    _language_setting: str
    _reload_flag: threading.Event
    _state: str  # "starting" | "idle" | "recording" | "processing"

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
        cursor_overlay: CursorOverlay | None = None,
        config_loader: ConfigLoader | None = None,
        device_setting: str = "auto",
        language_setting: str = "auto",
    ) -> None:
        self._recorder = recorder
        self._transcriber = transcriber
        self._inserter = inserter
        self._postprocessor = postprocessor
        self._overlay = overlay
        self._feedback = feedback
        self._key = key
        self._tray = tray
        self._cursor_overlay = cursor_overlay or _NullCursorOverlay()
        self._done = threading.Event()
        self._config_loader = config_loader
        self._device_setting = device_setting
        self._language_setting = language_setting
        self._reload_flag = threading.Event()
        self._state = "starting"

    def set_tray(self, tray: TrayIcon) -> None:
        """Attach a tray icon. Must be called before run()."""
        self._tray = tray

    def swap_model(self, size: str) -> bool:
        """Hot-swap the Whisper model. Refused while recording, processing, or starting.

        Returns True if the swap was applied, False if skipped.
        """
        if self._state != "idle":
            print(
                f"voxy: model swap skipped — state is {self._state!r}, wait until idle",
                flush=True,
            )
            return False
        lang = None if self._language_setting == "auto" else self._language_setting
        new_t = Transcriber(
            model_size=size,
            device=self._device_setting,
            language=lang,
        )
        self._transcriber = new_t
        actual = new_t.model_size
        cached = "cached" if new_t.is_cached() else "will download on first use"
        print(f"voxy: model → {actual} ({cached})", flush=True)
        return True

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
        self._state = "idle"
        if self._tray:
            self._tray.start()
            self._tray.set_state("idle")
        device = self._transcriber._ct2_device.upper()
        model = self._transcriber.model_size
        mic = AudioRecorder.default_input_name()
        print(f"voxy — hold hotkey to dictate. Ctrl-C to quit. [{model} on {device}]")
        print(f"voxy: input → {mic}", flush=True)

        if self._config_loader is not None:
            signal.signal(signal.SIGUSR1, self._on_sigusr1)
            reload_thread = threading.Thread(
                target=self._reload_watcher, daemon=True, name="voxy-reload"
            )
            reload_thread.start()

        try:
            if self._overlay._root:
                self._overlay.wait_loop()
            else:
                self._done.wait()
        except KeyboardInterrupt:
            pass
        finally:
            listener.stop()
            self._cursor_overlay.stop()
            if self._tray:
                self._tray.stop()

    def _on_sigusr1(self, signum: int, frame: object) -> None:
        self._reload_flag.set()

    def _reload_watcher(self) -> None:
        while not self._done.is_set():
            if self._reload_flag.wait(timeout=0.5):
                self._reload_flag.clear()
                if self._config_loader is None:
                    continue
                try:
                    cfg = self._config_loader.load()
                    self.swap_model(cfg.model.size)
                except Exception as e:
                    print(f"voxy: model reload failed: {e}", flush=True)

    def _on_press(self) -> None:
        self._state = "recording"
        self._overlay.show()
        self._cursor_overlay.show()
        self._feedback.play_start()
        self._recorder.start()
        if self._tray:
            self._tray.set_state("recording")
        print("voxy: recording…", flush=True)

    def _on_release(self) -> None:
        self._state = "processing"
        transcriber = self._transcriber  # snapshot — immune to concurrent swap
        audio = self._recorder.stop()
        self._overlay.processing()
        self._cursor_overlay.processing()
        self._feedback.play_stop()
        if self._tray:
            self._tray.set_state("processing")
        print("voxy: processing…", flush=True)

        def _pipeline() -> None:
            try:
                text = transcriber.transcribe(audio)
                text = self._postprocessor.process(text)
                if text:
                    print(f"voxy: {text}", flush=True)
                else:
                    print("voxy: (no speech detected)", flush=True)
                self._inserter.insert(text)
            except Exception as e:
                print(f"voxy error: {e}", flush=True)
            finally:
                self._state = "idle"
                self._overlay.hide()
                self._cursor_overlay.hide()
                if self._tray:
                    self._tray.set_state("idle")

        threading.Thread(target=_pipeline, daemon=True).start()
