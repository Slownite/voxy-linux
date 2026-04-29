"""Tests for audio feedback."""

from unittest.mock import MagicMock, patch

from voxy.audio import AudioFeedback
from voxy.config import UIConfig


def test_feedback_disabled():
    """Test that when disabled, play_start and play_stop do nothing."""
    config = UIConfig(audio_feedback=False)
    with patch("voxy.audio.sd") as mock_sd:
        feedback = AudioFeedback(config)
        feedback.play_start()
        feedback.play_stop()
        mock_sd.play.assert_not_called()


def test_feedback_enabled_plays_sound():
    """Test that when enabled, it reads the file and plays it."""
    config = UIConfig(audio_feedback=True)
    with patch("voxy.audio.sd") as mock_sd, \
         patch("voxy.audio.wave.open") as mock_wave, \
         patch("voxy.audio._get_sound_path") as mock_path:
        
        # Mock wave file reading
        mock_wf = MagicMock()
        mock_wf.getframerate.return_value = 16000
        mock_wf.getsampwidth.return_value = 2
        mock_wf.readframes.return_value = b"\x00\x00"
        mock_wave.return_value.__enter__.return_value = mock_wf
        
        feedback = AudioFeedback(config)
        
        feedback.play_start()
        mock_sd.play.assert_called()
        
        mock_sd.play.reset_mock()
        feedback.play_stop()
        mock_sd.play.assert_called()
