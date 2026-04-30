"""Tests for the Overlay UI."""

import tkinter as tk
from unittest.mock import MagicMock, patch

import pytest

from voxy.config import UIConfig
from voxy.overlay import OverlayUI


def test_overlay_disabled() -> None:
    """Test that when overlay is disabled, show/hide do nothing and no window is created."""
    config = UIConfig(overlay=False)
    with patch("voxy.overlay.tk") as mock_tk:
        overlay = OverlayUI(config)
        overlay.show()
        overlay.hide()
        mock_tk.Tk.assert_not_called()


def test_overlay_show_hide() -> None:
    """Test that show() and hide() call the correct window methods."""
    config = UIConfig(overlay=True)
    with patch("voxy.overlay.tk") as mock_tk:
        mock_root = MagicMock()
        mock_tk.Tk.return_value = mock_root

        overlay = OverlayUI(config)

        overlay.show()
        overlay._poll()
        mock_root.deiconify.assert_called_once()
        mock_root.update.assert_called()

        overlay.hide()
        overlay.hide()
        overlay._poll()
        mock_root.withdraw.assert_called()


def test_overlay_processing() -> None:
    """Test that processing() switches colour and label without hiding."""
    config = UIConfig(overlay=True)
    with patch("voxy.overlay.tk") as mock_tk:
        mock_root = MagicMock()
        mock_label = MagicMock()
        mock_tk.Tk.return_value = mock_root
        mock_tk.Label.return_value = mock_label

        overlay = OverlayUI(config)
        mock_root.withdraw.reset_mock()  # called once in __init__

        overlay.show()
        overlay._poll()
        mock_root.deiconify.assert_called_once()

        overlay.processing()
        overlay._poll()
        mock_root.configure.assert_called_with(bg="#ffaa00")
        mock_label.configure.assert_called_with(bg="#ffaa00", text="…")
        mock_root.withdraw.assert_not_called()


def test_overlay_geometry_corners() -> None:
    """Test geometry calculation for different corners."""
    with patch("voxy.overlay.tk") as mock_tk:
        mock_root = MagicMock()
        mock_root.winfo_screenwidth.return_value = 1920
        mock_root.winfo_screenheight.return_value = 1080
        mock_tk.Tk.return_value = mock_root

        # Test bottom-right: 1920-80-20=1820, 1080-28-20=1032
        config = UIConfig(overlay=True, overlay_corner="bottom-right")
        overlay = OverlayUI(config)
        overlay.show()
        overlay._poll()
        mock_root.geometry.assert_called_with("80x28+1820+1032")

        # Test top-left
        config = UIConfig(overlay=True, overlay_corner="top-left")
        overlay = OverlayUI(config)
        overlay.show()
        overlay._poll()
        mock_root.geometry.assert_called_with("80x28+20+20")

        # Test top-right: 1920-80-20=1820
        config = UIConfig(overlay=True, overlay_corner="top-right")
        overlay = OverlayUI(config)
        overlay.show()
        overlay._poll()
        mock_root.geometry.assert_called_with("80x28+1820+20")

        # Test bottom-left: 1080-28-20=1032
        config = UIConfig(overlay=True, overlay_corner="bottom-left")
        overlay = OverlayUI(config)
        overlay.show()
        overlay._poll()
        mock_root.geometry.assert_called_with("80x28+20+1032")


def test_overlay_tclerror_surfaced(capsys: pytest.CaptureFixture[str]) -> None:
    """TclError from tk.Tk() is printed to stderr and overlay is silently disabled."""
    config = UIConfig(overlay=True)
    with patch("voxy.overlay.tk") as mock_tk:
        mock_tk.TclError = tk.TclError
        mock_tk.Tk.side_effect = tk.TclError("no display")
        overlay = OverlayUI(config)
    assert overlay._root is None
    assert "overlay disabled" in capsys.readouterr().err


def test_poll_survives_tclerror_in_show() -> None:
    """_poll() must reschedule itself even when _show_internal() raises TclError."""
    config = UIConfig(overlay=True)
    with patch("voxy.overlay.tk") as mock_tk:
        mock_root = MagicMock()
        mock_tk.Tk.return_value = mock_root
        mock_tk.TclError = tk.TclError

        overlay = OverlayUI(config)
        mock_root.after.reset_mock()
        mock_root.deiconify.side_effect = tk.TclError("connection lost")

        overlay.show()
        overlay._poll()  # must not raise; next poll must be scheduled

        mock_root.after.assert_called_once_with(50, overlay._poll)
