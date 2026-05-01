"""Tests for ConfigLoader."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from voxy.config import Config, ConfigError, ConfigLoader, VOXY_CONFIG_ENV


def _write(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "config.toml"
    p.write_text(textwrap.dedent(content), encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# Missing file → defaults + file created
# ---------------------------------------------------------------------------

def test_missing_file_returns_defaults(tmp_path: Path) -> None:
    path = tmp_path / "voxy" / "config.toml"
    config = ConfigLoader(path).load()
    assert config == Config()


def test_missing_file_creates_default_file(tmp_path: Path) -> None:
    path = tmp_path / "voxy" / "config.toml"
    ConfigLoader(path).load()
    assert path.exists()
    assert "[hotkey]" in path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Valid full config
# ---------------------------------------------------------------------------

def test_valid_full_config(tmp_path: Path) -> None:
    path = _write(tmp_path, """
        [hotkey]
        key = "right_ctrl"

        [model]
        size = "base"
        language = "fr"
        fallback_language = "en"

        [insertion]
        method = "wayland"

        [post_processing]
        punctuation_commands = false
        auto_capitalize = false
        strip_fillers = true
        fillers = ["euh"]

        [post_processing.substitutions]
        "virgule" = ","

        [ui]
        overlay = false
        overlay_corner = "top-left"
        audio_feedback = true

        [logging]
        level = "debug"
    """)
    cfg = ConfigLoader(path).load()
    assert cfg.hotkey.key == "right_ctrl"
    assert cfg.model.size == "base"
    assert cfg.model.language == "fr"
    assert cfg.insertion.method == "wayland"
    assert cfg.post_processing.punctuation_commands is False
    assert cfg.post_processing.strip_fillers is True
    assert cfg.post_processing.fillers == ("euh",)
    assert cfg.post_processing.substitutions == {"virgule": ","}
    assert cfg.ui.overlay is False
    assert cfg.ui.overlay_corner == "top-left"
    assert cfg.ui.audio_feedback is True
    assert cfg.logging.level == "debug"


# ---------------------------------------------------------------------------
# Partial config — missing fields use defaults
# ---------------------------------------------------------------------------

def test_partial_config_uses_defaults(tmp_path: Path) -> None:
    path = _write(tmp_path, """
        [model]
        size = "large-v3"
    """)
    cfg = ConfigLoader(path).load()
    assert cfg.model.size == "large-v3"
    assert cfg.model.language == "auto"          # default
    assert cfg.hotkey.key == "right_alt"         # default
    assert cfg.logging.level == "info"           # default


# ---------------------------------------------------------------------------
# Invalid values → ConfigError
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# VOXY_CONFIG env var override
# ---------------------------------------------------------------------------

def test_env_var_used_when_xdg_absent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_file = _write(tmp_path, """
        [hotkey]
        key = "right_ctrl"
    """)
    monkeypatch.setattr("voxy.config.XDG_CONFIG_PATH", tmp_path / "nonexistent.toml")
    monkeypatch.setenv(VOXY_CONFIG_ENV, str(config_file))
    cfg = ConfigLoader().load()
    assert cfg.hotkey.key == "right_ctrl"


def test_env_var_overrides_xdg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    xdg_file = tmp_path / "xdg.toml"
    xdg_file.write_text('[hotkey]\nkey = "right_shift"\n', encoding="utf-8")
    env_file = tmp_path / "env.toml"
    env_file.write_text('[hotkey]\nkey = "right_ctrl"\n', encoding="utf-8")
    monkeypatch.setattr("voxy.config.XDG_CONFIG_PATH", xdg_file)
    monkeypatch.setenv(VOXY_CONFIG_ENV, str(env_file))
    cfg = ConfigLoader().load()
    assert cfg.hotkey.key == "right_ctrl"


def test_env_var_missing_file_returns_defaults(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(VOXY_CONFIG_ENV, str(tmp_path / "nonexistent.toml"))
    cfg = ConfigLoader().load()
    assert cfg == Config()


@pytest.mark.parametrize(("toml", "fragment"), [
    ('[model]\nsize = "giant"', r"\[model\] size"),
    ('[model]\ndevice = "rocm"', r"\[model\] device"),
    ('[insertion]\nmethod = "clipboard"', r"\[insertion\] method"),
    ('[logging]\nlevel = "verbose"', r"\[logging\] level"),
    ('[ui]\noverlay_corner = "center"', r"\[ui\] overlay_corner"),
    ('[post_processing]\nauto_capitalize = "yes"', r"\[post_processing\] auto_capitalize"),
    ('[hotkey]\nkey = ""', r"\[hotkey\] key"),
])
def test_invalid_value_raises(tmp_path: Path, toml: str, fragment: str) -> None:
    path = _write(tmp_path, toml)
    with pytest.raises(ConfigError, match=fragment):
        ConfigLoader(path).load()


# ---------------------------------------------------------------------------
# ModelConfig.device field
# ---------------------------------------------------------------------------

def test_model_config_device_default(tmp_path: Path) -> None:
    cfg = ConfigLoader(tmp_path / "absent.toml").load()
    assert cfg.model.device == "auto"


def test_model_config_device_valid_values(tmp_path: Path) -> None:
    for device in ("auto", "cpu", "cuda"):
        path = _write(tmp_path, f'[model]\ndevice = "{device}"\n')
        cfg = ConfigLoader(path).load()
        assert cfg.model.device == device


def test_model_config_device_invalid(tmp_path: Path) -> None:
    path = _write(tmp_path, '[model]\ndevice = "rocm"\n')
    with pytest.raises(ConfigError, match=r"\[model\] device"):
        ConfigLoader(path).load()
