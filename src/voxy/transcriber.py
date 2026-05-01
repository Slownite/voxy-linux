"""Transcriber — wraps faster-whisper for audio-to-text conversion."""

from __future__ import annotations

import logging
from pathlib import Path

import ctranslate2
import numpy as np
import numpy.typing as npt
from faster_whisper import WhisperModel

MODEL_CACHE_DIR: Path = Path.home() / ".cache" / "voxy" / "models"
DEFAULT_MODEL_SIZE: str = "small"
DEFAULT_DEVICE: str = "auto"

_log = logging.getLogger(__name__)

_COMPUTE_TYPE_PRIORITY: list[str] = ["int8_float16", "float16", "float32"]


def _resolve_device_and_compute(device: str) -> tuple[str, str]:
    """Return (ct2_device, compute_type) given a user device setting."""
    if device == "cpu":
        _log.info("voxy: device=cpu compute_type=int8")
        return "cpu", "int8"

    cuda_count = ctranslate2.get_cuda_device_count()

    if device == "cuda":
        if cuda_count == 0:
            _log.warning(
                "device='cuda' requested but no CUDA device found; falling back to CPU"
            )
            _log.info("voxy: device=cpu compute_type=int8")
            return "cpu", "int8"

    elif device == "auto":
        if cuda_count == 0:
            _log.info("voxy: device=cpu compute_type=int8")
            return "cpu", "int8"

    supported = ctranslate2.get_supported_compute_types("cuda")
    for ct in _COMPUTE_TYPE_PRIORITY:
        if ct in supported:
            _log.info("voxy: device=cuda compute_type=%s", ct)
            return "cuda", ct

    _log.info("voxy: device=cuda compute_type=float32 (fallback)")
    return "cuda", "float32"


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
    _ct2_device: str
    _compute_type: str

    def __init__(
        self,
        model_size: str = DEFAULT_MODEL_SIZE,
        device: str = DEFAULT_DEVICE,
    ) -> None:
        self._model_size = model_size
        self._ct2_device, self._compute_type = _resolve_device_and_compute(device)
        self._model = None

    def _get_model(self) -> WhisperModel:
        if self._model is None:
            MODEL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
            _log.info("voxy: loading model size=%s device=%s compute_type=%s",
                      self._model_size, self._ct2_device, self._compute_type)
            self._model = WhisperModel(
                self._model_size,
                device=self._ct2_device,
                compute_type=self._compute_type,
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
