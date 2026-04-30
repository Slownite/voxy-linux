"""daemon module — implemented in its own issue."""

import subprocess
from pathlib import Path


class DaemonManager:
    """Manages the systemd user service for voxy."""

    _SERVICE_TEMPLATE = """\
[Unit]
Description=voxy — local offline voice dictation for Linux

[Service]
Type=simple
ExecStart=voxy
Restart=on-failure
StateDirectory=voxy
StandardOutput=append:%S/voxy/voxy.log
StandardError=append:%S/voxy/voxy.log

[Install]
WantedBy=default.target
"""

    def __init__(self) -> None:
        self._service_path = Path.home() / ".config" / "systemd" / "user" / "voxy.service"
        self._log_dir = Path.home() / ".local" / "state" / "voxy"

    def install(self) -> None:
        self._service_path.parent.mkdir(parents=True, exist_ok=True)
        self._log_dir.mkdir(parents=True, exist_ok=True)
        self._service_path.write_text(self._SERVICE_TEMPLATE, encoding="utf-8")
        subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
        subprocess.run(["systemctl", "--user", "enable", "--now", "voxy.service"], check=True)
        print("Daemon installed and started.")

    def remove(self) -> None:
        subprocess.run(["systemctl", "--user", "disable", "--now", "voxy.service"], check=False)
        if self._service_path.exists():
            self._service_path.unlink()
        subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
        print("Daemon removed.")

    def status(self) -> None:
        subprocess.run(["systemctl", "--user", "status", "voxy.service"])
