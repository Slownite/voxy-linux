"""CLI entry point for voxy."""

import argparse

from voxy.app import App
from voxy.audio import AudioRecorder
from voxy.config import ConfigLoader
from voxy.inserter import TextInserter
from voxy.postprocess import PostProcessor
from voxy.transcriber import Transcriber


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="voxy",
        description="Local offline voice dictation for Linux.",
    )
    parser.add_argument(
        "--daemon",
        action="store_true",
        help="Install and enable the systemd user service.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="voxy 0.1.0",
    )
    parser.parse_args()
    config = ConfigLoader().load()
    App(
        AudioRecorder(),
        Transcriber(model_size=config.model.size),
        TextInserter(config.insertion.method),
        PostProcessor(config.post_processing),
        key=config.hotkey.key,
    ).run()


if __name__ == "__main__":
    main()
