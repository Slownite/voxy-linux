"""CLI entry point for voxy."""

import argparse

from voxy.app import App
from voxy.audio import AudioRecorder
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
    App(AudioRecorder(), Transcriber()).run()


if __name__ == "__main__":
    main()
