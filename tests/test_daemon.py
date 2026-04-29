"""Tests for DaemonManager."""

from unittest.mock import MagicMock, patch

from voxy.daemon import DaemonManager


@patch("voxy.daemon.subprocess.run")
@patch("voxy.daemon.Path.write_text")
@patch("voxy.daemon.Path.mkdir")
def test_daemon_install(mock_mkdir: MagicMock, mock_write: MagicMock, mock_run: MagicMock) -> None:
    """Test installing the systemd service."""
    daemon = DaemonManager()
    daemon.install()
    
    mock_mkdir.assert_called_with(parents=True, exist_ok=True)
    mock_write.assert_called_once()
    assert "ExecStart=" in mock_write.call_args[0][0]
    
    # Check systemctl calls
    mock_run.assert_any_call(["systemctl", "--user", "daemon-reload"], check=True)
    mock_run.assert_any_call(["systemctl", "--user", "enable", "--now", "voxy.service"], check=True)


@patch("voxy.daemon.subprocess.run")
@patch("voxy.daemon.Path.exists")
@patch("voxy.daemon.Path.unlink")
def test_daemon_remove(mock_unlink: MagicMock, mock_exists: MagicMock, mock_run: MagicMock) -> None:
    """Test removing the systemd service."""
    mock_exists.return_value = True
    daemon = DaemonManager()
    daemon.remove()
    
    mock_run.assert_any_call(["systemctl", "--user", "disable", "--now", "voxy.service"], check=False)
    mock_unlink.assert_called_once()
    mock_run.assert_any_call(["systemctl", "--user", "daemon-reload"], check=True)


@patch("voxy.daemon.subprocess.run")
def test_daemon_status(mock_run: MagicMock) -> None:
    """Test checking daemon status."""
    daemon = DaemonManager()
    daemon.status()
    mock_run.assert_called_once_with(["systemctl", "--user", "status", "voxy.service"])
