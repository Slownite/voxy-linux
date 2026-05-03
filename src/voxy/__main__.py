"""CLI entry point for voxy."""

import argparse

from voxy.app import App
from voxy.audio import AudioRecorder, AudioFeedback
from voxy.config import ConfigLoader, VALID_MODEL_SIZES
from voxy.inserter import TextInserter
from voxy.overlay import OverlayUI
from voxy.postprocess import PostProcessor
from voxy.transcriber import Transcriber

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
    if loader.is_first_run():
        chosen = _prompt_model()
        loader.write_default(model_size=chosen)
    config = loader.load()
    lang = None if config.model.language == "auto" else config.model.language

    app = App(
        AudioRecorder(),
        Transcriber(
            model_size=config.model.size,
            device=config.model.device,
            language=lang,
        ),
        TextInserter(config.insertion.method, notify=config.ui.notify),
        PostProcessor(config.post_processing),
        OverlayUI(config.ui),
        AudioFeedback(config.ui),
        key=config.hotkey.key,
    )

    if config.ui.tray:
        try:
            from voxy.tray import TrayIcon
            app._tray = TrayIcon(on_quit=app.stop)
        except ImportError as e:
            print(f"voxy: tray disabled — install dbus-next ({e})", flush=True)

    app.run()


if __name__ == "__main__":
    main()
