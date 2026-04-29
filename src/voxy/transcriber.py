"""Transcriber — wraps faster-whisper for audio-to-text conversion."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import numpy.typing as npt
from faster_whisper import WhisperModel

MODEL_CACHE_DIR: Path = Path.home() / ".cache" / "voxy" / "models"
DEFAULT_MODEL_SIZE: str = "small"


class Transcriber:
    """Transcribes a numpy audio array to text using faster-whisper.

    The model is downloaded on first use and cached in
    ``~/.cache/voxy/models/`` for subsequent runs.

    Usage::

        t = Transcriber()
        text = t.transcribe(audio_array)
    """

    _model: WhisperModel | None
    _model_size: str

    def __init__(self, model_size: str = DEFAULT_MODEL_SIZE) -> None:
        self._model_size = model_size
        self._model = None

    def _get_model(self) -> WhisperModel:
        if self._model is None:
            MODEL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
            self._model = WhisperModel(
                self._model_size,
                device="cpu",
                compute_type="int8",
                download_root=str(MODEL_CACHE_DIR),
            )
        return self._model

    def transcribe(self, audio: npt.NDArray[np.float32]) -> str:
        """Return transcribed text for *audio* (1-D float32, 16 kHz).

        Language is auto-detected per utterance. Returns an empty string
        for silent / blank audio.
        """
        if audio.size == 0:
            return ""
        model = self._get_model()
        segments, _info = model.transcribe(
            audio,
            language=None,  # auto-detect
            beam_size=5,
        )
        return "".join(segment.text for segment in segments).strip()
