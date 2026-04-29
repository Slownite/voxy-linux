# voxy — Product Requirements Document

> Published: 2026-04-29 | GitHub: Slownite/voxy#1

## Problem Statement

Linux users who want fast, offline voice dictation have no good native option. Existing tools like WisprFlow are macOS/Windows-only, cloud-dependent, or subscription-based. Users who work across multiple languages, value privacy, or operate in air-gapped environments are left without a viable solution. The friction of manually switching to a dictation interface or copying text between apps further reduces productivity.

## Solution

voxy is a local, offline voice dictation tool for Linux (X11 and Wayland). The user holds a configurable hotkey, speaks, and releases — the transcribed text is pasted directly into whatever window is currently active. It runs entirely on-device using a local Whisper model via faster-whisper, requires no internet connection, and supports any language Whisper can detect. It ships as a Nix flake with a NixOS module for seamless integration, and works on any Linux distribution.

## User Stories

1. As a Linux user, I want to dictate text into any application, so that I can write faster without switching tools.
2. As a user, I want push-to-talk activation, so that dictation only happens when I intend it.
3. As a user, I want to configure my hotkey at runtime, so that I can choose a key that fits my workflow without modifying code.
4. As a user, I want the hotkey to default to Right Alt, so that I can start using the tool immediately without configuration.
5. As a user, I want my audio to be processed locally, so that my dictated content never leaves my machine.
6. As a multilingual user, I want the language to be auto-detected per dictation, so that I can switch languages mid-session without reconfiguring.
7. As a user, I want a configurable fallback language, so that low-confidence detections resolve to a sensible default.
8. As a user, I want the transcribed text to be inserted into the active window automatically, so that I don't have to manually paste.
9. As an X11 user, I want text insertion to use xclip and xdotool, so that pasting works reliably in my environment.
10. As a Wayland user, I want text insertion to use wl-clipboard and ydotool, so that pasting works reliably in my environment.
11. As a user on either X11 or Wayland, I want the display server to be detected automatically, so that I don't need to configure the insertion method manually.
12. As a user, I want to override the auto-detected insertion method in config, so that I can force a specific backend if needed.
13. As a user, I want a small floating overlay to appear while I'm recording, so that I always know when the microphone is active.
14. As a user, I want the overlay to appear in a configurable screen corner, so that it doesn't obstruct my work.
15. As a user, I want the overlay to disappear as soon as I release the hotkey, so that it stays out of my way when not recording.
16. As a user, I want spoken punctuation words like "comma" and "period" to be converted to symbols, so that I can punctuate naturally while dictating.
17. As a user, I want the first letter of dictated text to be auto-capitalized, so that the output is properly formatted.
18. As a user, I want optional filler word stripping (uh, um), so that I can get cleaner output without manually editing.
19. As a user, I want to define custom word substitutions in my config, so that I can adapt the post-processing to my vocabulary and workflow.
20. As a user, I want all post-processing to be individually toggleable, so that I can opt out of transformations I don't want.
21. As a user, I want audio feedback (sounds on record start/stop) to be configurable, so that I can enable it if helpful or disable it in quiet environments.
22. As a user, I want voxy to run in the foreground from a terminal, so that I can easily observe logs and debug issues.
23. As a user, I want a --daemon flag that installs a systemd user service, so that voxy starts automatically on login.
24. As a NixOS user, I want a services.voxy NixOS module, so that I can enable voxy declaratively in my system configuration.
25. As a user, I want config stored at ~/.config/voxy/config.toml, so that it follows XDG conventions.
26. As a user, I want models cached at ~/.cache/voxy/models/, so that downloads are not repeated on each run.
27. As a user, I want logs written to ~/.local/share/voxy/voxy.log, so that I can review past sessions.
28. As a user, I want the config file to use TOML format, so that it is human-readable and supports comments.
29. As a user, I want the app to start with sensible defaults if no config file exists, so that I can use it immediately after install.
30. As a user, I want the model size to be configurable, so that I can trade accuracy for speed as my hardware allows.
31. As a user, I want a clear error message if I am not in the input group, so that I know exactly how to fix hotkey capture permissions.
32. As a user, I want the hotkey listener to fall back to pynput if evdev is unavailable, so that the tool works in more environments.
33. As a NixOS user, I want the flake to provide a dev shell with all dependencies, so that I can develop and test without manual setup.
34. As a user, I want audio to be buffered in memory during recording and discarded after insertion, so that no audio files are written to disk.

## Implementation Decisions

### Modules

**Deep modules (simple interface, rich implementation):**

- **ConfigLoader** — reads TOML config from XDG path, applies typed defaults, validates fields, exposes a single immutable `Config` dataclass. All other modules consume this object; none read config directly.
- **AudioRecorder** — wraps sounddevice; exposes `start()` and `stop() → np.ndarray`. Handles device selection, sample rate, in-memory buffering. No audio is written to disk.
- **Transcriber** — wraps faster-whisper; exposes `transcribe(audio: np.ndarray) → str`. Manages model loading and caching, language auto-detection, and fallback. Model is loaded once at startup.
- **PostProcessor** — exposes `process(text: str) → str`. Applies punctuation command substitution, auto-capitalization, filler stripping, and custom substitutions in a configurable pipeline. Pure function — no side effects.
- **TextInserter** — exposes `insert(text: str) → None`. Detects X11 vs Wayland at init time, selects the appropriate clipboard and paste tools, writes text to clipboard, simulates Ctrl+V.

**Orchestration modules:**

- **HotkeyListener** — wraps evdev (primary) and pynput (fallback); emits `on_press` / `on_release` callbacks for the configured key. Checks input group membership at startup.
- **OverlayUI** — small always-on-top tkinter window; exposes `show()` / `hide()`. Positioned at a configurable screen corner.
- **DaemonManager** — installs, removes, and queries a systemd user service unit for voxy.
- **App** — event loop that wires all modules together. On key press: show overlay, start recording. On key release: stop recording, transcribe, post-process, insert, hide overlay.

### Key technical decisions

- Display server detected via `$WAYLAND_DISPLAY` / `$DISPLAY` environment variables at runtime; can be overridden in config.
- faster-whisper `small` model is the default; model size is a config field.
- Language is set to `"auto"` by default; faster-whisper performs per-utterance detection.
- Hotkey is captured via evdev reading `/dev/input` events; user must be in the `input` group.
- Config format is TOML; `tomllib` (stdlib, Python 3.11+) is used with `tomli` as a fallback.
- All punctuation command substitutions and custom substitutions are defined in the config file, not hardcoded.
- Audio is never persisted to disk.

### Packaging

- Distributed as a Nix flake with a dev shell, a package output, and a NixOS module.
- NixOS module exposes `services.voxy.enable` and key config options as NixOS options.
- External CLI tools (xclip, xdotool, wl-clipboard, ydotool) are declared as runtime dependencies in the flake.

## Testing Decisions

**What makes a good test:** tests verify observable behavior through the module's public interface only. No mocking of internal implementation details. Tests should remain valid even if the internals are rewritten.

**Modules to test (tests ship with each slice):**

- **ConfigLoader** — fixture TOML files: valid config, missing fields (defaults applied), invalid values (errors raised), missing file (defaults returned).
- **PostProcessor** — pure function; exhaustive unit tests: punctuation commands, capitalization, filler stripping on/off, custom substitutions, combinations. No mocking needed.
- **Transcriber** — integration tests with short fixture wav files; assert transcription returns a non-empty string in the correct language. Test model loading and language fallback.
- **TextInserter** — test X11/Wayland detection logic; mock subprocess calls to xclip/xdotool/wl-copy/ydotool and assert correct commands are invoked for each environment.

**Modules not tested:** OverlayUI (GUI), HotkeyListener (hardware), DaemonManager (systemd), App (integration complexity outweighs benefit at this stage).

## Out of Scope

- GPU / CUDA support (noted as a future upgrade path; faster-whisper supports it without API changes)
- Wake-word / always-on detection mode
- Speaker diarization
- Audio feedback sound files (feature is stubbed; sounds can be added later)
- Windows or macOS support
- A graphical settings UI
- Real-time streaming transcription (full utterance is transcribed on key release)
- Cloud/remote model inference

## Further Notes

- The project is named **voxy** — CLI command, config dir, and NixOS module all use this name.
- WisprFlow (https://wisprflow.ai/) is the UX reference; the goal is feature parity for the core dictation loop on Linux.
- Build order: flake.nix → AudioRecorder + Transcriber → HotkeyListener → TextInserter → OverlayUI → PostProcessor → DaemonManager → NixOS module.
- On NixOS, users must add `users.extraGroups = ["input"]` for evdev hotkey capture to work.

## Issues

| # | Title |
|---|---|
| [#2](https://github.com/Slownite/voxy/issues/2) | Nix dev shell & project scaffold |
| [#3](https://github.com/Slownite/voxy/issues/3) | Core audio → transcription pipeline |
| [#4](https://github.com/Slownite/voxy/issues/4) | Full config system (TOML + XDG) |
| [#5](https://github.com/Slownite/voxy/issues/5) | Push-to-talk hotkey capture |
| [#6](https://github.com/Slownite/voxy/issues/6) | Text insertion (X11 & Wayland) |
| [#7](https://github.com/Slownite/voxy/issues/7) | Recording overlay UI |
| [#8](https://github.com/Slownite/voxy/issues/8) | Post-processing pipeline |
| [#9](https://github.com/Slownite/voxy/issues/9) | Audio feedback |
| [#10](https://github.com/Slownite/voxy/issues/10) | Daemon mode + systemd user service |
| [#11](https://github.com/Slownite/voxy/issues/11) | NixOS module |
