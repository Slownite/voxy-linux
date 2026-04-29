"""AudioRecorder — in-memory audio capture via sounddevice."""

from __future__ import annotations

import threading

import numpy as np
import numpy.typing as npt
import sounddevice as sd

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
