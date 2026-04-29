"""PostProcessor — text transformation pipeline."""

from __future__ import annotations

import re

from .config import PostProcessingConfig


class PostProcessor:
    """Applies text transformations: punctuation, capitalization, filler stripping."""

    _config: PostProcessingConfig

    def __init__(self, config: PostProcessingConfig) -> None:
        self._config = config

    def process(self, text: str) -> str:
        """Apply all enabled transformations in order."""
        if not text:
            return text

        text = text.strip()

        if self._config.strip_fillers:
            for filler in self._config.fillers:
                pattern = r'(?i)\b' + re.escape(filler) + r'\b'
                text = re.sub(pattern, '', text)
            text = re.sub(r'[^\S\r\n]+', ' ', text).strip()

        if self._config.punctuation_commands:
            for cmd, sub in self._config.substitutions.items():
                pattern = r'(?i)\b' + re.escape(cmd) + r'\b'
                text = re.sub(pattern, sub, text)
            
            # Clean up extra spaces before punctuation
            text = re.sub(r'[^\S\r\n]+([,\.\!\?\:\;])', r'\1', text)
            # Clean up extra horizontal spaces again
            text = re.sub(r'[^\S\r\n]+', ' ', text).strip()
            # Clean up spaces around newlines
            text = '\n'.join(line.strip() for line in text.split('\n'))
            
        if self._config.auto_capitalize and text:
            text = text[0].upper() + text[1:]

        return text
