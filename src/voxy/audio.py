"""AudioRecorder — in-memory audio capture via sounddevice."""

from __future__ import annotations

import shutil
import subprocess
import threading
from typing import Any

import numpy as np
import numpy.typing as npt
import sounddevice as sd

_PACTL_TIMEOUT: float = 0.5


def _resolve_default_pactl_source() -> str:
    """Return the description of the system default source via pactl, or ''."""
    if not shutil.which("pactl"):
        return ""
    try:
        result = subprocess.run(
            ["pactl", "get-default-source"],
            capture_output=True, text=True, check=False, timeout=_PACTL_TIMEOUT,
        )
        if result.returncode != 0:
            return ""
        default_name = result.stdout.strip()
        if not default_name:
            return ""

        listing = subprocess.run(
            ["pactl", "list", "sources"],
            capture_output=True, text=True, check=False, timeout=_PACTL_TIMEOUT,
        )
        if listing.returncode != 0:
            return default_name  # fall back to the raw source name

        current_name = ""
        for raw_line in listing.stdout.splitlines():
            line = raw_line.strip()
            if line.startswith("Name:"):
                current_name = line.split(":", 1)[1].strip()
            elif line.startswith("Description:") and current_name == default_name:
                return line.split(":", 1)[1].strip()
        return default_name
    except (subprocess.TimeoutExpired, OSError):
        return ""

SAMPLE_RATE: int = 16_000  # Hz — faster-whisper expects 16 kHz
CHANNELS: int = 1


class AudioRecorder:
    """Captures audio from the default input device into a numpy array.

    Usage::

        recorder = AudioRecorder()
        recorder.start()
        # ... user holds key ...
        audio = recorder.stop()  # shape (N,), dtype float32
    """

    _chunks: list[npt.NDArray[np.float32]]
    _stream: sd.InputStream | None
    _lock: threading.Lock

    def __init__(self) -> None:
        self._chunks = []
        self._stream = None
        self._lock = threading.Lock()

    @staticmethod
    def default_input_name() -> str:
        """Return the default input device's display name.

        If sounddevice reports a generic alias ("default", "pulse", "sysdefault"),
        resolve the underlying source via pactl and append it in parentheses.
        """
        try:
            info: dict[str, Any] = sd.query_devices(kind="input")  # type: ignore[assignment]
            sd_name = str(info.get("name", "")) if isinstance(info, dict) else ""
        except Exception:
            sd_name = ""

        if not sd_name:
            return "(unknown)"

        if sd_name.lower() in {"default", "pulse", "sysdefault", "pipewire"}:
            real = _resolve_default_pactl_source()
            if real:
                return f"{sd_name} ({real})"
        return sd_name

    def start(self) -> None:
        """Begin capturing audio from the default input device."""
        if self._stream is not None:
            return
        self._chunks = []
        self._stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype="float32",
            callback=self._callback,
        )
        self._stream.start()

    def stop(self) -> npt.NDArray[np.float32]:
        """Halt recording and return captured audio as a 1-D float32 array."""
        if self._stream is None:
            return np.zeros(0, dtype=np.float32)
        self._stream.stop()
        self._stream.close()
        self._stream = None
        with self._lock:
            if not self._chunks:
                return np.zeros(0, dtype=np.float32)
            audio = np.concatenate(self._chunks, axis=0).flatten()
        return audio

    def _callback(
        self,
        indata: npt.NDArray[np.float32],
        frames: int,
        time: object,
        status: sd.CallbackFlags,
    ) -> None:
        with self._lock:
            self._chunks.append(indata.copy())


import wave
from pathlib import Path
from .config import UIConfig


def _get_sound_path(name: str) -> Path:
    return Path(__file__).parent / name


class AudioFeedback:
    """Plays start and stop audio cues if enabled."""

    def __init__(self, config: UIConfig) -> None:
        self._config = config
        self._start_audio: tuple[npt.NDArray[Any], int] | None = None
        self._stop_audio: tuple[npt.NDArray[Any], int] | None = None
        
        if self._config.audio_feedback:
            self._start_audio = self._load_wav("start.wav")
            self._stop_audio = self._load_wav("stop.wav")

    def _load_wav(self, filename: str) -> tuple[npt.NDArray[Any], int] | None:
        path = _get_sound_path(filename)
        if not path.exists():
            return None
        with wave.open(str(path), 'rb') as wf:
            framerate = wf.getframerate()
            sampwidth = wf.getsampwidth()
            n_frames = wf.getnframes()
            data = wf.readframes(n_frames)
            
            dtype: Any
            if sampwidth == 2:
                dtype = np.int16
            elif sampwidth == 4:
                dtype = np.int32
            else:
                dtype = np.uint8
                
            audio_array = np.frombuffer(data, dtype=dtype)
            return audio_array, framerate

    def play_start(self) -> None:
        if self._config.audio_feedback and self._start_audio:
            data, fs = self._start_audio
            sd.play(data, samplerate=fs)

    def play_stop(self) -> None:
        if self._config.audio_feedback and self._stop_audio:
            data, fs = self._stop_audio
            sd.play(data, samplerate=fs)
