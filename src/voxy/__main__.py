"""CLI entry point for voxy."""

import argparse

from voxy.app import App
from voxy.audio import AudioRecorder, AudioFeedback
from voxy.config import ConfigLoader
from voxy.inserter import TextInserter
from voxy.overlay import OverlayUI
from voxy.postprocess import PostProcessor
from voxy.transcriber import Transcriber


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
        
    config = ConfigLoader().load()
    App(
        AudioRecorder(),
        Transcriber(model_size=config.model.size),
        TextInserter(config.insertion.method),
        PostProcessor(config.post_processing),
        OverlayUI(config.ui),
        AudioFeedback(config.ui),
        key=config.hotkey.key,
    ).run()


if __name__ == "__main__":
    main()
