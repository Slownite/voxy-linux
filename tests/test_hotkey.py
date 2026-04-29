"""Tests for HotkeyListener and check_input_group."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from unittest.mock import patch

import pytest

from voxy.hotkey import HotkeyListener, check_input_group, _evdev_code, _pynput_key, _keys_match


# ---------------------------------------------------------------------------
# Key resolution helpers
# ---------------------------------------------------------------------------

def test_evdev_code_known_key() -> None:
    code = _evdev_code("right_alt")
    assert code is not None
    assert isinstance(code, int)


def test_evdev_code_unknown_key() -> None:
    assert _evdev_code("not_a_real_key_xyz") is None


def test_pynput_key_modifier() -> None:
    from pynput import keyboard as kb
    key = _pynput_key("right_alt")
    assert key == kb.Key.alt_r


def test_pynput_key_char() -> None:
    from pynput import keyboard as kb
    key = _pynput_key("a")
    assert isinstance(key, kb.KeyCode)


def test_keys_match_key() -> None:
    from pynput import keyboard as kb
    assert _keys_match(kb.Key.alt_r, kb.Key.alt_r)
    assert not _keys_match(kb.Key.ctrl, kb.Key.alt_r)


def test_keys_match_keycode() -> None:
    from pynput import keyboard as kb
    a = kb.KeyCode.from_char("a")
    assert _keys_match(kb.KeyCode.from_char("a"), a)
    assert not _keys_match(kb.KeyCode.from_char("b"), a)


# ---------------------------------------------------------------------------
# HotkeyListener via pynput simulation
# ---------------------------------------------------------------------------

def _make_listener(
    key: str,
    on_press: Callable[[], None],
    on_release: Callable[[], None],
) -> HotkeyListener:
    """Return a HotkeyListener forced onto the pynput backend."""
    listener = HotkeyListener(key=key, on_press=on_press, on_release=on_release)
    # Force pynput backend regardless of evdev availability
    with patch.object(listener, "_evdev_available", return_value=False):
        listener.start()
    return listener


def test_listener_fires_press_and_release() -> None:
    from pynput import keyboard as kb
    from pynput.keyboard import Controller

    pressed: list[bool] = []
    released: list[bool] = []

    listener = _make_listener("a", lambda: pressed.append(True), lambda: released.append(True))
    time.sleep(0.05)  # let thread start

    ctrl = Controller()
    ctrl.press("a")
    time.sleep(0.05)
    ctrl.release("a")
    time.sleep(0.05)

    listener.stop()

    assert pressed == [True]
    assert released == [True]


def test_listener_stop_ends_thread() -> None:
    listener = _make_listener("a", lambda: None, lambda: None)
    time.sleep(0.05)
    listener.stop()
    assert listener._thread is not None
    listener._thread.join(timeout=1.0)
    assert not listener._thread.is_alive()


# ---------------------------------------------------------------------------
# check_input_group
# ---------------------------------------------------------------------------

def test_check_input_group_passes_when_member() -> None:
    import grp
    import os
    gid = grp.getgrnam("input").gr_gid if _input_group_exists() else 0
    with patch("os.getgroups", return_value=[gid]):
        check_input_group()  # must not raise


def test_check_input_group_raises_when_not_member() -> None:
    if not _input_group_exists():
        pytest.skip("no input group on this system")
    with patch("os.getgroups", return_value=[]):
        with pytest.raises(RuntimeError, match="input"):
            check_input_group()


def _input_group_exists() -> bool:
    import grp
    try:
        grp.getgrnam("input")
        return True
    except KeyError:
        return False
