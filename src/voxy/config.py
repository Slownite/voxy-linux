"""ConfigLoader — reads TOML config from XDG path, applies typed defaults."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

XDG_CONFIG_PATH: Path = Path.home() / ".config" / "voxy" / "config.toml"
VOXY_CONFIG_ENV: str = "VOXY_CONFIG"

MODEL_SIZE_ORDER: list[str] = [
    "auto", "tiny", "tiny.en", "base", "base.en", "small", "small.en",
    "medium", "medium.en", "large-v1", "large-v2", "large-v3",
]
VALID_MODEL_SIZES: frozenset[str] = frozenset(MODEL_SIZE_ORDER)
_VALID_DEVICE_OPTIONS: frozenset[str] = frozenset({"auto", "cpu", "cuda"})
_VALID_INSERTION_METHODS: frozenset[str] = frozenset({"auto", "x11", "wayland"})
_VALID_LOG_LEVELS: frozenset[str] = frozenset({"debug", "info", "warning", "error"})
_VALID_OVERLAY_CORNERS: frozenset[str] = frozenset(
    {"top-left", "top-right", "bottom-left", "bottom-right"}
)


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ConfigError(message)


def _as_table(raw: Any, section: str) -> dict[str, Any]:
    _require(isinstance(raw, dict), f"[{section}] must be a table, got {type(raw).__name__}")
    return cast(dict[str, Any], raw)


def _as_bool(raw: Any, field: str) -> bool:
    _require(isinstance(raw, bool), f"{field} must be a boolean, got {raw!r}")
    return cast(bool, raw)


def _as_nonempty_str(raw: Any, field: str) -> str:
    _require(isinstance(raw, str) and bool(raw), f"{field} must be a non-empty string, got {raw!r}")
    return cast(str, raw)


def _as_one_of(raw: Any, valid: frozenset[str], field: str) -> str:
    _require(raw in valid, f"{field} {raw!r} is invalid. Valid values: {sorted(valid)}")
    return cast(str, raw)


def _as_str_list(raw: Any, field: str) -> list[str]:
    _require(
        isinstance(raw, list) and all(isinstance(v, str) for v in raw),
        f"{field} must be a list of strings",
    )
    return cast(list[str], raw)


def _as_str_dict(raw: Any, field: str) -> dict[str, str]:
    _require(
        isinstance(raw, dict) and all(isinstance(k, str) and isinstance(v, str) for k, v in raw.items()),
        f"{field} must be a table of string → string",
    )
    return cast(dict[str, str], raw)


# ---------------------------------------------------------------------------
# Config dataclasses
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class HotkeyConfig:
    key: str = "right_alt"


@dataclass(frozen=True)
class ModelConfig:
    size: str = "auto"
    language: str = "auto"
    device: str = "auto"


@dataclass(frozen=True)
class InsertionConfig:
    method: str = "auto"


@dataclass(frozen=True)
class PostProcessingConfig:
    punctuation_commands: bool = True
    auto_capitalize: bool = True
    strip_fillers: bool = False
    fillers: tuple[str, ...] = ("uh", "um", "hmm")
    substitutions: dict[str, str] = field(
        default_factory=lambda: {
            "new line": "\n",
            "new paragraph": "\n\n",
            "comma": ",",
            "period": ".",
            "question mark": "?",
            "exclamation mark": "!",
            "colon": ":",
            "semicolon": ";",
        }
    )


@dataclass(frozen=True)
class UIConfig:
    overlay: bool = True
    overlay_corner: str = "bottom-right"
    audio_feedback: bool = False
    notify: bool = True
    tray: bool = True
    cursor_overlay: bool = True


@dataclass(frozen=True)
class LoggingConfig:
    level: str = "info"


@dataclass(frozen=True)
class Config:
    hotkey: HotkeyConfig = field(default_factory=HotkeyConfig)
    model: ModelConfig = field(default_factory=ModelConfig)
    insertion: InsertionConfig = field(default_factory=InsertionConfig)
    post_processing: PostProcessingConfig = field(default_factory=PostProcessingConfig)
    ui: UIConfig = field(default_factory=UIConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)


class ConfigError(ValueError):
    """Raised when a config field has an invalid value."""


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

class ConfigLoader:
    """Reads TOML config from XDG path, validates, and returns a Config.

    Missing file → all-defaults. Missing fields → per-field defaults.
    Invalid values → ConfigError with a descriptive message.
    """

    _config_path: Path

    def __init__(self, config_path: Path | None = None) -> None:
        if config_path is not None:
            self._config_path = config_path
        elif (env := os.environ.get(VOXY_CONFIG_ENV)):
            self._config_path = Path(env)
        elif XDG_CONFIG_PATH.exists():
            self._config_path = XDG_CONFIG_PATH
        else:
            self._config_path = XDG_CONFIG_PATH

    @property
    def config_path(self) -> Path:
        return self._config_path

    def is_first_run(self) -> bool:
        return not self._config_path.exists()

    def load(self) -> Config:
        """Return a fully populated Config from file.

        On first run (file absent) the XDG directory and a commented default
        config file are created, then all-defaults are returned.
        """
        if not self._config_path.exists():
            self.write_default()
            return Config()
        with open(self._config_path, "rb") as fh:
            raw: dict[str, Any] = tomllib.load(fh)
        return Config(
            hotkey=_parse_hotkey(_as_table(raw.get("hotkey", {}), "hotkey")),
            model=_parse_model(_as_table(raw.get("model", {}), "model")),
            insertion=_parse_insertion(_as_table(raw.get("insertion", {}), "insertion")),
            post_processing=_parse_post_processing(_as_table(raw.get("post_processing", {}), "post_processing")),
            ui=_parse_ui(_as_table(raw.get("ui", {}), "ui")),
            logging=_parse_logging(_as_table(raw.get("logging", {}), "logging")),
        )

    def set_model_size(self, size: str) -> None:
        """Rewrite [model] size = "..." in the config file."""
        import re
        if not self._config_path.exists():
            self.write_default(model_size=size)
            return
        text = self._config_path.read_text(encoding="utf-8")
        # Match `size = "..."` only inside [model] section (stops before next section)
        new_text, n = re.subn(
            r'(\[model\][^\[]*?)(size\s*=\s*")[^"]*(")',
            r'\1\g<2>' + size + r'\3',
            text,
            count=1,
        )
        if n == 0:
            # size key absent — insert immediately after [model] header
            new_text, m = re.subn(r'(\[model\])', rf'\1\nsize = "{size}"', text, count=1)
            if m == 0:
                raise ConfigError(
                    f"[model] section missing in {self._config_path}; cannot update model size"
                )
        self._config_path.write_text(new_text, encoding="utf-8")

    def write_default(self, model_size: str = "auto") -> None:
        """Create XDG dir and write a commented default config file."""
        self._config_path.parent.mkdir(parents=True, exist_ok=True)
        toml = _DEFAULT_CONFIG_TOML.replace('size = "auto"', f'size = "{model_size}"', 1)
        self._config_path.write_text(toml, encoding="utf-8")


_DEFAULT_CONFIG_TOML: str = """\
# voxy configuration — generated on first run.
# All fields are optional; omitted fields use the defaults shown here.

[hotkey]
# Key to hold for push-to-talk. Uses pynput/evdev key names.
key = "right_alt"

[model]
# Whisper model size. Options: auto, tiny, tiny.en, base, base.en, small, small.en,
# medium, medium.en, large-v1, large-v2, large-v3
# "auto" picks the largest size your CPU can run near-realtime (or "small" on GPU).
size = "auto"

# Language for transcription. "auto" detects per utterance.
language = "auto"

# Inference device. Options: auto, cpu, cuda
# "auto" uses GPU when available and falls back to CPU silently.
device = "auto"

[insertion]
# How to insert text. Options: auto, x11, wayland
method = "auto"

[post_processing]
punctuation_commands = true
auto_capitalize = true
strip_fillers = false
fillers = ["uh", "um", "hmm"]

[post_processing.substitutions]
"new line"         = "\\n"
"new paragraph"    = "\\n\\n"
"comma"            = ","
"period"           = "."
"question mark"    = "?"
"exclamation mark" = "!"
"colon"            = ":"
"semicolon"        = ";"

[ui]
overlay = true
# Corner for the overlay. Options: top-left, top-right, bottom-left, bottom-right
overlay_corner = "bottom-right"
audio_feedback = false
# Send a desktop notification when transcript is copied to clipboard.
notify = true
# Show a system tray icon (StatusNotifierItem) with status + menu.
tray = true
# Draw a green frame and status rect anchored to the mouse cursor while
# recording. X11 / XWayland and Hyprland (Wayland) only.
cursor_overlay = true

[logging]
# Options: debug, info, warning, error
level = "info"
"""


# ---------------------------------------------------------------------------
# Section parsers
# ---------------------------------------------------------------------------

def _parse_hotkey(t: dict[str, Any]) -> HotkeyConfig:
    return HotkeyConfig(
        key=_as_nonempty_str(t.get("key", HotkeyConfig.key), "[hotkey] key"),
    )


def _parse_model(t: dict[str, Any]) -> ModelConfig:
    return ModelConfig(
        size=_as_one_of(t.get("size", ModelConfig.size), VALID_MODEL_SIZES, "[model] size"),
        language=_as_nonempty_str(t.get("language", ModelConfig.language), "[model] language"),
        device=_as_one_of(t.get("device", ModelConfig.device), _VALID_DEVICE_OPTIONS, "[model] device"),
    )


def _parse_insertion(t: dict[str, Any]) -> InsertionConfig:
    return InsertionConfig(
        method=_as_one_of(t.get("method", InsertionConfig.method), _VALID_INSERTION_METHODS, "[insertion] method"),
    )


def _parse_post_processing(t: dict[str, Any]) -> PostProcessingConfig:
    defaults = PostProcessingConfig()
    raw_subs = t.get("substitutions")
    substitutions = (
        _as_str_dict(raw_subs, "[post_processing] substitutions")
        if raw_subs is not None
        else dict(defaults.substitutions)
    )
    return PostProcessingConfig(
        punctuation_commands=_as_bool(t.get("punctuation_commands", defaults.punctuation_commands), "[post_processing] punctuation_commands"),
        auto_capitalize=_as_bool(t.get("auto_capitalize", defaults.auto_capitalize), "[post_processing] auto_capitalize"),
        strip_fillers=_as_bool(t.get("strip_fillers", defaults.strip_fillers), "[post_processing] strip_fillers"),
        fillers=tuple(_as_str_list(t.get("fillers", list(defaults.fillers)), "[post_processing] fillers")),
        substitutions=substitutions,
    )


def _parse_ui(t: dict[str, Any]) -> UIConfig:
    defaults = UIConfig()
    return UIConfig(
        overlay=_as_bool(t.get("overlay", defaults.overlay), "[ui] overlay"),
        overlay_corner=_as_one_of(t.get("overlay_corner", defaults.overlay_corner), _VALID_OVERLAY_CORNERS, "[ui] overlay_corner"),
        audio_feedback=_as_bool(t.get("audio_feedback", defaults.audio_feedback), "[ui] audio_feedback"),
        notify=_as_bool(t.get("notify", defaults.notify), "[ui] notify"),
        tray=_as_bool(t.get("tray", defaults.tray), "[ui] tray"),
        cursor_overlay=_as_bool(t.get("cursor_overlay", defaults.cursor_overlay), "[ui] cursor_overlay"),
    )


def _parse_logging(t: dict[str, Any]) -> LoggingConfig:
    return LoggingConfig(
        level=_as_one_of(t.get("level", LoggingConfig.level), _VALID_LOG_LEVELS, "[logging] level"),
    )
