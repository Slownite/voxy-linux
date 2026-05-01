"""Tests for Transcriber — verifies real faster-whisper transcription."""

from __future__ import annotations

import logging
import wave
from pathlib import Path

import ctranslate2
import numpy as np
import numpy.typing as npt
import pytest

from voxy.transcriber import Transcriber

FIXTURES = Path(__file__).parent / "fixtures"

_CUDA_AVAILABLE = ctranslate2.get_cuda_device_count() > 0


def load_wav(path: Path) -> npt.NDArray[np.float32]:
    """Read a WAV file and return a normalised float32 array at 16 kHz."""
    with wave.open(str(path), "rb") as wf:
        frames = wf.readframes(wf.getnframes())
        n_channels = wf.getnchannels()
        sampwidth = wf.getsampwidth()

    if sampwidth == 2:
        audio = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
    else:
        raise ValueError(f"Unsupported sample width: {sampwidth}")

    if n_channels > 1:
        audio = audio.reshape(-1, n_channels).mean(axis=1)

    return audio


@pytest.fixture(scope="module")
def transcriber() -> Transcriber:
    return Transcriber()


def test_transcribe_english(transcriber: Transcriber) -> None:
    audio = load_wav(FIXTURES / "en_hello.wav")
    result = transcriber.transcribe(audio)
    assert isinstance(result, str)
    assert len(result) > 0
    assert "hello" in result.lower()


def test_transcribe_french(transcriber: Transcriber) -> None:
    # espeak-ng synthetic speech + small model → word-level accuracy unreliable,
    # but the pipeline must handle non-English audio without crashing and return
    # a non-empty string (proving multilingual support works end-to-end).
    audio = load_wav(FIXTURES / "fr_bonjour.wav")
    result = transcriber.transcribe(audio)
    assert isinstance(result, str)
    assert len(result) > 0


def test_transcribe_empty_audio(transcriber: Transcriber) -> None:
    empty: npt.NDArray[np.float32] = np.zeros(0, dtype=np.float32)
    result = transcriber.transcribe(empty)
    assert result == ""


# ---------------------------------------------------------------------------
# Device selection — CPU paths (run everywhere)
# ---------------------------------------------------------------------------

def test_cpu_explicit_transcribes() -> None:
    t = Transcriber(device="cpu")
    audio = load_wav(FIXTURES / "en_hello.wav")
    result = t.transcribe(audio)
    assert isinstance(result, str)
    assert "hello" in result.lower()


def test_auto_falls_back_to_cpu_silently(caplog: pytest.LogCaptureFixture) -> None:
    if _CUDA_AVAILABLE:
        pytest.skip("CUDA present — auto will use GPU, not CPU fallback")
    with caplog.at_level(logging.DEBUG, logger="voxy.transcriber"):
        t = Transcriber(device="auto")
    warning_msgs = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert not warning_msgs, "auto should be silent on CPU-only machine"
    audio = load_wav(FIXTURES / "en_hello.wav")
    assert isinstance(t.transcribe(audio), str)


def test_cuda_explicit_falls_back_with_warning(caplog: pytest.LogCaptureFixture) -> None:
    if _CUDA_AVAILABLE:
        pytest.skip("CUDA present — no fallback occurs")
    with caplog.at_level(logging.WARNING, logger="voxy.transcriber"):
        t = Transcriber(device="cuda")
    assert any("warning" in r.message.lower() or r.levelno >= logging.WARNING for r in caplog.records)
    audio = load_wav(FIXTURES / "en_hello.wav")
    assert isinstance(t.transcribe(audio), str)


# ---------------------------------------------------------------------------
# Device selection — GPU paths (auto-skip when no CUDA)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not _CUDA_AVAILABLE, reason="No CUDA device present")
def test_cuda_explicit_transcribes_gpu() -> None:
    t = Transcriber(device="cuda")
    audio = load_wav(FIXTURES / "en_hello.wav")
    result = t.transcribe(audio)
    assert isinstance(result, str)
    assert len(result) > 0


@pytest.mark.skipif(not _CUDA_AVAILABLE, reason="No CUDA device present")
def test_auto_uses_cuda_gpu() -> None:
    t = Transcriber(device="auto")
    audio = load_wav(FIXTURES / "en_hello.wav")
    result = t.transcribe(audio)
    assert isinstance(result, str)
    assert len(result) > 0
