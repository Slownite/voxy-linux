"""Tests for App._on_release — issue #23: async transcription pipeline."""

from __future__ import annotations

import threading
from typing import cast
from unittest.mock import MagicMock

from voxy.app import App
from voxy.audio import AudioFeedback, AudioRecorder
from voxy.inserter import TextInserter
from voxy.overlay import OverlayUI
from voxy.postprocess import PostProcessor
from voxy.transcriber import Transcriber

_TIMEOUT = 1.0  # seconds — background thread must complete within this


def _default_mocks() -> tuple[MagicMock, MagicMock, MagicMock, MagicMock]:
    """Return (transcriber, postprocessor, inserter, overlay) with happy-path defaults."""
    t: MagicMock = MagicMock()
    t.transcribe.return_value = "hello"
    p: MagicMock = MagicMock()
    p.process.side_effect = lambda text: text
    i: MagicMock = MagicMock()
    o: MagicMock = MagicMock()
    return t, p, i, o


def _make_app(
    t: MagicMock, p: MagicMock, i: MagicMock, o: MagicMock
) -> App:
    return App(
        recorder=cast(AudioRecorder, MagicMock()),
        transcriber=cast(Transcriber, t),
        inserter=cast(TextInserter, i),
        postprocessor=cast(PostProcessor, p),
        overlay=cast(OverlayUI, o),
        feedback=cast(AudioFeedback, MagicMock()),
    )


def _hide_event(o: MagicMock) -> threading.Event:
    """Wire o.hide() to set and return an Event."""
    ev: threading.Event = threading.Event()
    o.hide.side_effect = lambda: ev.set()
    return ev


def _slow_transcriber(gate: threading.Event) -> MagicMock:
    """Return a transcriber mock that blocks on *gate* (5 s max) then returns 'hello'."""
    t: MagicMock = MagicMock()

    def _transcribe(_audio: object) -> str:
        gate.wait(timeout=5.0)
        return "hello"

    t.transcribe.side_effect = _transcribe
    return t


# ---------------------------------------------------------------------------
# Tracer bullet: _on_release() must not block on transcription
# ---------------------------------------------------------------------------

def test_on_release_is_nonblocking() -> None:
    """_on_release() must return before transcription completes."""
    gate: threading.Event = threading.Event()
    _, p, i, o = _default_mocks()
    t = _slow_transcriber(gate)
    hide_ev = _hide_event(o)

    app = _make_app(t, p, i, o)

    rel = threading.Thread(target=app._on_release, daemon=True)
    rel.start()
    rel.join(timeout=0.2)

    try:
        assert not rel.is_alive(), (
            "_on_release() blocked — pipeline must run in a background thread"
        )
        o.hide.assert_not_called()  # transcription still in progress
    finally:
        gate.set()  # always unblock so the thread can exit

    assert hide_ev.wait(timeout=_TIMEOUT), "overlay.hide() never called after pipeline"
    o.hide.assert_called_once()


# ---------------------------------------------------------------------------
# overlay.processing() is called synchronously before the background thread
# ---------------------------------------------------------------------------

def test_processing_called_before_pipeline() -> None:
    """overlay.processing() is called immediately on key release."""
    gate: threading.Event = threading.Event()
    _, p, i, o = _default_mocks()
    t = _slow_transcriber(gate)
    hide_ev = _hide_event(o)

    app = _make_app(t, p, i, o)

    # Run in daemon thread so we don't hang in RED state (current sync impl blocks here)
    rel = threading.Thread(target=app._on_release, daemon=True)
    rel.start()
    rel.join(timeout=0.1)  # enough for processing() to be called in both sync/async paths

    o.processing.assert_called_once()

    gate.set()
    hide_ev.wait(timeout=_TIMEOUT)
    rel.join(timeout=_TIMEOUT)


# ---------------------------------------------------------------------------
# overlay.hide() called on every outcome (finally in background thread)
# ---------------------------------------------------------------------------

def test_hide_called_when_transcription_raises() -> None:
    """overlay.hide() is called even if transcription raises."""
    t, p, i, o = _default_mocks()
    t.transcribe.side_effect = RuntimeError("model error")
    hide_ev = _hide_event(o)

    app = _make_app(t, p, i, o)
    app._on_release()

    assert hide_ev.wait(timeout=_TIMEOUT), "overlay.hide() not called after transcription error"
    o.hide.assert_called_once()


def test_hide_called_when_postprocessor_raises() -> None:
    """overlay.hide() is called even if postprocessor raises."""
    t, p, i, o = _default_mocks()
    p.process.side_effect = RuntimeError("postprocess error")
    hide_ev = _hide_event(o)

    app = _make_app(t, p, i, o)
    app._on_release()

    assert hide_ev.wait(timeout=_TIMEOUT), "overlay.hide() not called after postprocess error"
    o.hide.assert_called_once()


def test_hide_called_when_inserter_raises() -> None:
    """overlay.hide() is called even if inserter raises."""
    t, p, i, o = _default_mocks()
    i.insert.side_effect = RuntimeError("insert error")
    hide_ev = _hide_event(o)

    app = _make_app(t, p, i, o)
    app._on_release()

    assert hide_ev.wait(timeout=_TIMEOUT), "overlay.hide() not called after insert error"
    o.hide.assert_called_once()
