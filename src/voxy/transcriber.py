"""Transcriber — wraps faster-whisper for audio-to-text conversion."""

from __future__ import annotations

import ctypes
import logging
import os
from pathlib import Path

import ctranslate2
import numpy as np
import numpy.typing as npt
from faster_whisper import WhisperModel
from faster_whisper.utils import _MODELS as _MODEL_REPO_IDS
from huggingface_hub import snapshot_download

try:
    from huggingface_hub.utils import get_token as _hf_get_token
except ImportError:  # older hf_hub
    _hf_get_token = None  # type: ignore[assignment]

MODEL_CACHE_DIR: Path = Path.home() / ".cache" / "voxy" / "models"
DEFAULT_MODEL_SIZE: str = "auto"
DEFAULT_DEVICE: str = "auto"
DEFAULT_LANGUAGE: str | None = None

_MODEL_ALLOW_PATTERNS: list[str] = [
    "config.json",
    "preprocessor_config.json",
    "model.bin",
    "tokenizer.json",
    "vocabulary.*",
]


def _hf_authenticated() -> bool:
    """True if the user has an HF token via env or `huggingface-cli login`."""
    if os.environ.get("HF_TOKEN"):
        return True
    if _hf_get_token is None:
        return False
    try:
        return bool(_hf_get_token())
    except Exception:
        return False


def _physical_core_count() -> int:
    """Best-effort physical core count. OpenMP/CTranslate2 scales with physical, not SMT."""
    sched = getattr(os, "sched_getaffinity", None)
    logical = len(sched(0)) if sched else (os.cpu_count() or 1)
    try:
        pairs: set[tuple[str, str]] = set()
        socket = ""
        core = ""
        with open("/proc/cpuinfo") as f:
            for line in f:
                if line.startswith("physical id"):
                    socket = line.split(":", 1)[1].strip()
                elif line.startswith("core id"):
                    core = line.split(":", 1)[1].strip()
                elif line.strip() == "" and socket and core:
                    pairs.add((socket, core))
                    socket = core = ""
        if pairs:
            return max(1, min(len(pairs), logical))
    except OSError:
        pass
    return max(1, logical)


def _has_cpu_flag(flag: str) -> bool:
    try:
        with open("/proc/cpuinfo") as f:
            for line in f:
                if line.startswith("flags"):
                    return flag in line.split()
    except OSError:
        return False
    return False


def _auto_model_size_for_cpu() -> str:
    """Pick whisper size matching CPU budget.

    Heuristic by physical cores + int8 acceleration. Targets ~realtime PTT latency.
    VNNI (AVX-VNNI / AVX-512 VNNI) gives ~2-4x int8 throughput.
    """
    cores = _physical_core_count()
    vnni = _has_cpu_flag("avx512_vnni") or _has_cpu_flag("avx_vnni")
    avx2 = _has_cpu_flag("avx2")
    if vnni and cores >= 8:
        return "small"
    if avx2 and cores >= 4:
        return "base"
    return "tiny"

_log = logging.getLogger(__name__)

_COMPUTE_TYPE_PRIORITY: list[str] = ["int8_float16", "float16", "float32"]

# Versioned sonames ctranslate2 4.x lazy-dlopen at inference time.
# Update _CT2_CUBLAS_VERSION when upgrading ctranslate2 to a new major.
_CT2_CUBLAS_VERSION = "12"


def _cuda_device_count() -> int:
    try:
        return ctranslate2.get_cuda_device_count()
    except (OSError, RuntimeError) as exc:
        _log.warning("voxy: CUDA unavailable (%s); falling back to CPU", exc)
        return 0


def _cuda_libs_available() -> bool:
    """Return False if any CUDA shared library ctranslate2 needs cannot be loaded.

    ctranslate2 lazy-dlopen versioned names at inference time. Probe early so
    we fall back to CPU before loading the model, not mid-transcription.
    """
    v = _CT2_CUBLAS_VERSION
    for lib in (f"libcublas.so.{v}", f"libcublasLt.so.{v}"):
        try:
            ctypes.CDLL(lib)
        except OSError as exc:
            _log.debug("voxy: CUDA library %s cannot be loaded (%s); falling back to CPU", lib, exc)
            return False
    return True


def _resolve_device_and_compute(device: str) -> tuple[str, str]:
    """Return (ct2_device, compute_type) given a user device setting."""
    if device == "cpu":
        return "cpu", "int8"

    cuda_count = _cuda_device_count()

    if device == "cuda" and cuda_count == 0:
        _log.warning("device='cuda' requested but no CUDA device found; falling back to CPU")
        return "cpu", "int8"
    if device == "auto" and cuda_count == 0:
        return "cpu", "int8"

    if not _cuda_libs_available():
        return "cpu", "int8"

    try:
        supported = ctranslate2.get_supported_compute_types("cuda")
    except (OSError, RuntimeError) as exc:
        _log.warning("voxy: CUDA compute type query failed (%s); falling back to CPU", exc)
        return "cpu", "int8"

    for ct in _COMPUTE_TYPE_PRIORITY:
        if ct in supported:
            return "cuda", ct

    return "cuda", "float32"


def _run_transcribe(
    model: WhisperModel,
    audio: npt.NDArray[np.float32],
    language: str | None,
) -> str:
    segments, _info = model.transcribe(
        audio,
        language=language,
        beam_size=1,
        vad_filter=True,
        condition_on_previous_text=False,
    )
    return "".join(segment.text for segment in segments).strip()


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
    _model_size_was_auto: bool
    _ct2_device: str
    _compute_type: str
    _language: str | None
    _cpu_threads: int

    def __init__(
        self,
        model_size: str = DEFAULT_MODEL_SIZE,
        device: str = DEFAULT_DEVICE,
        language: str | None = DEFAULT_LANGUAGE,
        cpu_threads: int | None = None,
    ) -> None:
        self._ct2_device, self._compute_type = _resolve_device_and_compute(device)
        _log.info("voxy: device=%s compute_type=%s", self._ct2_device, self._compute_type)
        self._model_size_was_auto = model_size == "auto"
        if self._model_size_was_auto:
            self._model_size = (
                _auto_model_size_for_cpu() if self._ct2_device == "cpu" else "small"
            )
            _log.info("voxy: auto-selected model size=%s", self._model_size)
        else:
            self._model_size = model_size
        self._language = language
        self._cpu_threads = cpu_threads if cpu_threads is not None else _physical_core_count()
        self._model = None

    @property
    def model_size(self) -> str:
        return self._model_size

    @property
    def cache_path(self) -> Path:
        """Local cache directory for this model (may not exist yet)."""
        return MODEL_CACHE_DIR / f"models--Systran--faster-whisper-{self._model_size}"

    def is_cached(self) -> bool:
        """Return True if the model weights are fully present on disk.

        Checks each snapshot dir for ``model.bin`` so a partial download
        (e.g. interrupted by Ctrl+C) is not treated as cached.
        """
        snapshots = self.cache_path / "snapshots"
        if not snapshots.is_dir():
            return False
        for snap in snapshots.iterdir():
            if snap.is_dir() and (snap / "model.bin").exists():
                return True
        return False

    def prefetch(self) -> None:
        """Download the model with visible tqdm progress, then load it.

        faster_whisper hardcodes a disabled tqdm in its download helper, so
        ``snapshot_download`` is called directly here with the default tqdm
        class. The subsequent ``WhisperModel()`` load reuses these files.
        """
        if not _hf_authenticated():
            print(
                "voxy: downloading anonymously — set $HF_TOKEN or run "
                "`huggingface-cli login` for higher Hugging Face rate limits.",
                flush=True,
            )
        # huggingface_hub emits an "unauthenticated requests" warning mid-
        # download via its logger, interleaving into tqdm output. Silence
        # it for the duration of the fetch.
        hf_logger = logging.getLogger("huggingface_hub")
        prev_level = hf_logger.level
        hf_logger.setLevel(logging.ERROR)
        try:
            repo_id = _MODEL_REPO_IDS.get(self._model_size, self._model_size)
            MODEL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
            snapshot_download(
                repo_id,
                cache_dir=str(MODEL_CACHE_DIR),
                allow_patterns=_MODEL_ALLOW_PATTERNS,
            )
        finally:
            hf_logger.setLevel(prev_level)
        self._get_model()

    def _get_model(self) -> WhisperModel:
        if self._model is None:
            MODEL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
            threads = self._cpu_threads if self._ct2_device == "cpu" else 0
            _log.info(
                "voxy: loading model size=%s device=%s compute_type=%s cpu_threads=%d",
                self._model_size, self._ct2_device, self._compute_type, threads,
            )
            self._model = WhisperModel(
                self._model_size,
                device=self._ct2_device,
                compute_type=self._compute_type,
                download_root=str(MODEL_CACHE_DIR),
                cpu_threads=threads,
                num_workers=1,
            )
        return self._model

    def transcribe(self, audio: npt.NDArray[np.float32]) -> str:
        """Return transcribed text for *audio* (1-D float32, 16 kHz).

        If ``language`` is None, whisper auto-detects per utterance; otherwise
        the configured language is forced. Returns "" for silent / blank audio.
        """
        if audio.size == 0:
            return ""
        try:
            return _run_transcribe(self._get_model(), audio, self._language)
        except (OSError, RuntimeError) as exc:
            if self._ct2_device == "cpu":
                raise
            _log.warning("voxy: CUDA inference failed (%s); retrying on CPU", exc)
            self._model = None
            self._ct2_device = "cpu"
            self._compute_type = "int8"
            if self._model_size_was_auto:
                self._model_size = _auto_model_size_for_cpu()
                _log.info("voxy: re-auto-selected model size=%s for CPU", self._model_size)
            _log.info("voxy: permanently switched to CPU for this session")
            return _run_transcribe(self._get_model(), audio, self._language)
