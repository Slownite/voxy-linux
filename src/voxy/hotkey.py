"""HotkeyListener — evdev primary, pynput fallback."""

from __future__ import annotations

import io
import logging
import os
import sys
import threading
from collections.abc import Callable

import evdev
import evdev.ecodes as ecodes


def _try_import_pynput() -> object | None:
    # Suppress the noisy "XDG_RUNTIME_DIR not set" / xauth print that pynput
    # emits on Wayland when its X11 backend can't connect.
    if os.environ.get("WAYLAND_DISPLAY"):
        saved, sys.stdout = sys.stdout, io.StringIO()
        try:
            from pynput import keyboard as _kb
            return _kb
        except ImportError:
            return None
        finally:
            sys.stdout = saved
    else:
        try:
            from pynput import keyboard as _kb
            return _kb
        except ImportError:
            return None


_kb_module = _try_import_pynput()

# ---------------------------------------------------------------------------
# Key-name resolution
# ---------------------------------------------------------------------------

_EVDEV_KEY_MAP: dict[str, int] = {
    name.removeprefix("KEY_").lower().replace("_", ""): code
    for name, code in ecodes.ecodes.items()
    if name.startswith("KEY_") and isinstance(code, int)
}


def _evdev_code(key: str) -> int | None:
    return _EVDEV_KEY_MAP.get(key.lower().replace("_", "").replace(" ", ""))


_PYNPUT_KEY_NAMES: set[str] = (
    {name for name in dir(_kb_module.Key) if not name.startswith("_")}
    if _kb_module is not None else set()
)


def _normalise_for_pynput(key: str) -> str:
    """Convert config key names to pynput Key attribute names.

    Handles the ``right_alt`` → ``alt_r`` and ``left_ctrl`` → ``ctrl``
    patterns by rewriting ``{side}_{key}`` → ``{key}_{r}`` or ``{key}``.
    """
    parts = key.lower().split("_")
    if len(parts) >= 2 and parts[0] in ("right", "left"):
        side = parts[0]
        rest = "_".join(parts[1:])
        candidate = f"{rest}_r" if side == "right" else rest
        if candidate in _PYNPUT_KEY_NAMES:
            return candidate
    return key.lower()


def _pynput_key(key: str) -> object:
    assert _kb_module is not None
    normalised = _normalise_for_pynput(key)
    pynput_attr = getattr(_kb_module.Key, normalised, None)
    if pynput_attr is not None:
        return pynput_attr
    return _kb_module.KeyCode.from_char(key)


def _keys_match(key: object, target: object) -> bool:
    assert _kb_module is not None
    if isinstance(target, _kb_module.Key):
        return bool(key == target)
    if isinstance(target, _kb_module.KeyCode) and isinstance(key, _kb_module.KeyCode):
        return bool(key.char == target.char)
    return False


# ---------------------------------------------------------------------------
# HotkeyListener
# ---------------------------------------------------------------------------

class HotkeyListener:
    """Fires on_press / on_release callbacks for a configured hotkey.

    Uses evdev (reads from /dev/input) as primary backend; falls back to
    pynput if evdev finds no accessible keyboard devices (e.g. missing
    ``input`` group membership on systems where that applies).
    """

    _key: str
    _on_press: Callable[[], None]
    _on_release: Callable[[], None]
    _thread: threading.Thread | None
    _stop_event: threading.Event

    def __init__(
        self,
        key: str,
        on_press: Callable[[], None],
        on_release: Callable[[], None],
    ) -> None:
        self._key = key
        self._on_press = on_press
        self._on_release = on_release
        self._thread = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        """Begin listening in a background daemon thread."""
        self._stop_event.clear()
        backend = self._run_evdev if self._evdev_available() else self._run_pynput
        self._thread = threading.Thread(target=backend, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Signal the listener thread to exit."""
        self._stop_event.set()

    # ------------------------------------------------------------------
    # Backend selection
    # ------------------------------------------------------------------

    def _evdev_available(self) -> bool:
        """True if we can open at least one keyboard device via evdev."""
        code = _evdev_code(self._key)
        if code is None:
            return False
        for path in evdev.list_devices():
            try:
                dev = evdev.InputDevice(path)
                caps = dev.capabilities()
                if code in caps.get(ecodes.EV_KEY, []):
                    return True
            except OSError:
                continue
        return False

    # ------------------------------------------------------------------
    # evdev backend
    # ------------------------------------------------------------------

    def _run_evdev(self) -> None:
        code = _evdev_code(self._key)
        assert code is not None  # guaranteed by _evdev_available

        devices = self._find_evdev_devices(code)
        if not devices:
            self._run_pynput()
            return

        pressed = False
        pressed_lock = threading.Lock()

        _log = logging.getLogger(__name__)

        def run_device(dev: evdev.InputDevice) -> None:  # type: ignore[type-arg]
            nonlocal pressed
            try:
                for event in dev.read_loop():
                    if self._stop_event.is_set():
                        break
                    if event.type != ecodes.EV_KEY or event.code != code:
                        continue
                    with pressed_lock:
                        if event.value == 1 and not pressed:
                            pressed = True
                            self._on_press()
                        elif event.value == 0 and pressed:
                            pressed = False
                            self._on_release()
            except OSError as exc:
                _log.debug("evdev device lost (%s); hotkey listener falling back to pynput", exc)
            finally:
                dev.close()

        threads = [
            threading.Thread(target=run_device, args=(dev,), daemon=True)
            for dev in devices
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All device threads exited. If we weren't asked to stop, the devices
        # were lost (disconnected / re-enumerated). Fall back to pynput so the
        # service remains functional.
        if not self._stop_event.is_set():
            _log.info("All evdev devices gone; switching to pynput backend")
            self._run_pynput()

    def _find_evdev_devices(self, code: int) -> list[evdev.InputDevice]:  # type: ignore[type-arg]
        """Return all input devices that report the given key code."""
        found = []
        for path in evdev.list_devices():
            try:
                dev = evdev.InputDevice(path)
                caps = dev.capabilities()
                if code in caps.get(ecodes.EV_KEY, []):
                    found.append(dev)
                else:
                    dev.close()
            except OSError:
                continue
        return found

    # ------------------------------------------------------------------
    # pynput fallback
    # ------------------------------------------------------------------

    def _run_pynput(self) -> None:
        if _kb_module is None:
            raise RuntimeError(
                "pynput is not installed; voxy cannot fall back from evdev.\n"
                "  Install pynput or ensure the user is in the 'input' group so evdev works."
            )
        target = _pynput_key(self._key)
        pressed = False

        def on_press(key: object) -> None:
            nonlocal pressed
            if not pressed and _keys_match(key, target):
                pressed = True
                self._on_press()

        def on_release(key: object) -> None:
            nonlocal pressed
            if pressed and _keys_match(key, target):
                pressed = False
                self._on_release()

        with _kb_module.Listener(on_press=on_press, on_release=on_release) as listener:
            self._stop_event.wait()
            listener.stop()

