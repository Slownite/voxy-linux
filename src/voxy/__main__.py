"""CLI entry point for voxy."""

import os
import sys

# gtk4-layer-shell must be dlopened before libwayland-client; if not, layer
# surface init silently fails and the cursor overlay is invisible.
# Re-exec with LD_PRELOAD set if running on Wayland and not already preloaded.
_LAYER_SHELL_SO = "/usr/lib/libgtk4-layer-shell.so"
_PRELOAD_MARKER = "_VOXY_LAYER_SHELL_PRELOADED"
if (
    os.environ.get("WAYLAND_DISPLAY")
    and os.path.exists(_LAYER_SHELL_SO)
    and not os.environ.get(_PRELOAD_MARKER)
):
    _prev = os.environ.get("LD_PRELOAD", "")
    os.environ["LD_PRELOAD"] = f"{_LAYER_SHELL_SO}:{_prev}".strip(":")
    os.environ[_PRELOAD_MARKER] = "1"
    os.execvp(sys.executable, [sys.executable, "-m", "voxy"] + sys.argv[1:])

# Force huggingface_hub's pure-Python backend so model downloads show tqdm
# progress bars. Must run before any hf_hub / faster_whisper import.
os.environ.setdefault("HF_HUB_DISABLE_XET", "1")

import argparse
import signal
from pathlib import Path

from voxy.app import App
from voxy.audio import AudioRecorder, AudioFeedback
from voxy.config import ConfigError, ConfigLoader, VALID_MODEL_SIZES
from voxy.inserter import TextInserter
from voxy.overlay import OverlayUI
from voxy.postprocess import PostProcessor
from voxy.transcriber import Transcriber

_STATE_DIR: Path = Path.home() / ".local" / "state" / "voxy"
_PID_FILE: Path = _STATE_DIR / "voxy.pid"

_MODEL_MENU: list[tuple[str, str]] = [
    ("auto",       "detect best size for your CPU/GPU (default)"),
    ("tiny",       "~39 MB  — fastest, lowest accuracy"),
    ("base",       "~74 MB  — fast, decent accuracy"),
    ("small",      "~244 MB — good balance"),
    ("medium",     "~769 MB — high accuracy, slower"),
    ("large-v3",   "~1.5 GB — best accuracy, slowest"),
]


def _prompt_model() -> str:
    print("\nFirst run — choose a Whisper model size:")
    print("  English-only variants (e.g. tiny.en) are faster for English-only use.\n")
    for i, (name, desc) in enumerate(_MODEL_MENU, 1):
        marker = " *" if name == "auto" else "  "
        print(f"  {i}.{marker}{name:<12} {desc}")
    print()
    while True:
        try:
            raw = input("Enter number or model name [default: auto]: ").strip()
        except EOFError:
            return "auto"
        if not raw:
            return "auto"
        if raw.isdigit():
            idx = int(raw) - 1
            if 0 <= idx < len(_MODEL_MENU):
                return _MODEL_MENU[idx][0]
        if raw in VALID_MODEL_SIZES:
            return raw
        print(f"  Invalid: {raw!r}. Enter 1-{len(_MODEL_MENU)} or a model name.")


def _write_pid() -> None:
    _STATE_DIR.mkdir(parents=True, exist_ok=True)
    _PID_FILE.write_text(str(os.getpid()), encoding="utf-8")


def _remove_pid() -> None:
    _PID_FILE.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="voxy",
        description="Local offline voice dictation for Linux.",
    )
    parser.add_argument(
        "--daemon",
        choices=["install", "remove", "status"],
        help="Manage the systemd user service.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="voxy 0.1.0",
    )
    parser.add_argument(
        "--set-model",
        metavar="SIZE",
        help=(
            f"Hot-swap the Whisper model in a running voxy instance. "
            f"Valid sizes: {', '.join(sorted(VALID_MODEL_SIZES))}"
        ),
    )
    args = parser.parse_args()

    if args.daemon:
        from voxy.daemon import DaemonManager
        manager = DaemonManager()
        if args.daemon == "install":
            manager.install()
        elif args.daemon == "remove":
            manager.remove()
        elif args.daemon == "status":
            manager.status()
        return

    loader = ConfigLoader()

    if args.set_model:
        size = args.set_model
        if size not in VALID_MODEL_SIZES:
            print(f"voxy: invalid model size {size!r}. Valid: {sorted(VALID_MODEL_SIZES)}")
            sys.exit(1)
        if not _PID_FILE.exists():
            print("voxy: no running instance (PID file not found at ~/.local/state/voxy/voxy.pid)")
            sys.exit(1)
        pid = int(_PID_FILE.read_text(encoding="utf-8").strip())
        try:
            loader.set_model_size(size)
        except ConfigError as e:
            print(f"voxy: {e}")
            sys.exit(1)
        try:
            os.kill(pid, signal.SIGUSR1)
            print(f"voxy: model change to {size!r} sent to PID {pid} — takes effect when idle")
        except ProcessLookupError:
            print(f"voxy: PID {pid} not found (stale PID file?)")
            _PID_FILE.unlink(missing_ok=True)
            sys.exit(1)
        return

    first_run = loader.is_first_run()
    if first_run:
        chosen = _prompt_model()
        loader.write_default(model_size=chosen)
    config = loader.load()
    lang = None if config.model.language == "auto" else config.model.language

    transcriber = Transcriber(
        model_size=config.model.size,
        device=config.model.device,
        language=lang,
    )
    if config.model.size == "auto":
        print(f"voxy: auto-selected model size = {transcriber.model_size}", flush=True)

    cache_display = _shorten_home(transcriber.cache_path)
    if transcriber.is_cached():
        print(f"voxy: model {transcriber.model_size} cached at {cache_display}", flush=True)
    else:
        print(
            f"\nvoxy: downloading whisper model ({transcriber.model_size}) "
            f"to {cache_display} — this only happens once.\n",
            flush=True,
        )
        try:
            transcriber.prefetch()
        except KeyboardInterrupt:
            print("\nvoxy: download cancelled.", flush=True)
            return
        except Exception as e:
            print(f"voxy: model download failed: {e}", flush=True)
            return
        print("voxy: model ready.\n", flush=True)

    from voxy.cursor_overlay import build_cursor_overlay, _NullCursorOverlay

    import dataclasses  # noqa: PLC0415

    if os.environ.get("WAYLAND_DISPLAY"):
        # Wayland: cursor overlay uses GTK, no Tk root needed.  Build first so
        # we can suppress the corner overlay when the cursor overlay is active.
        cursor_ov = build_cursor_overlay(config.ui)
        ui_cfg = (dataclasses.replace(config.ui, overlay=False)
                  if not isinstance(cursor_ov, _NullCursorOverlay) else config.ui)
        overlay = OverlayUI(ui_cfg)
    else:
        # X11: cursor overlay shares the Tk root from OverlayUI — create
        # overlay first, then wire up cursor_ov with the Tk root.
        overlay = OverlayUI(config.ui)
        cursor_ov = build_cursor_overlay(config.ui, tk_root=overlay._root)
        if not isinstance(cursor_ov, _NullCursorOverlay):
            overlay.disable_corner()
    app = App(
        AudioRecorder(),
        transcriber,
        TextInserter(config.insertion.method, notify=config.ui.notify),
        PostProcessor(config.post_processing),
        overlay,
        AudioFeedback(config.ui),
        key=config.hotkey.key,
        cursor_overlay=cursor_ov,
        config_loader=loader,
        device_setting=config.model.device,
        language_setting=config.model.language,
    )

    if config.ui.tray:
        try:
            from voxy.tray import TrayIcon

            def _on_model_change(size: str) -> None:
                loader.set_model_size(size)
                app.swap_model(size)

            app.set_tray(TrayIcon(
                on_quit=app.stop,
                on_model_change=_on_model_change,
                get_model=lambda: app._transcriber.model_size,
            ))
        except ImportError as e:
            print(f"voxy: tray disabled — install dbus-next ({e})", flush=True)

    _write_pid()
    try:
        app.run()
    finally:
        _remove_pid()


def _shorten_home(path: Path) -> str:
    """Replace $HOME with ~ for terser display."""
    s = str(path)
    home = str(Path.home())
    return "~" + s[len(home):] if s.startswith(home) else s


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
