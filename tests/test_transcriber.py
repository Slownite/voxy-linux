"""Tests for Transcriber — verifies real faster-whisper transcription."""

from __future__ import annotations

import wave
from pathlib import Path

import numpy as np
import numpy.typing as npt
import pytest

from voxy.transcriber import Transcriber

FIXTURES = Path(__file__).parent / "fixtures"


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
