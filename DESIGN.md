# voxy — Design Document

> Local, CPU-based voice dictation for Linux (X11 & Wayland)
> Derived from grill-me session: 2026-04-29

## Concept

voxy is a local alternative to WisprFlow. Hold a hotkey, speak, release — transcribed text is pasted into whatever window is active. No cloud, no subscription, runs fully offline using a local Whisper model.

---

## Design Decisions

### Trigger mechanism
**Push-to-talk** — hold a configurable hotkey to record, release to transcribe and paste.

Rationale: precise, no silence-detection tuning, no accidental captures, mirrors WisprFlow UX.

---

### Hotkey
**Fully configurable at runtime**, defaulting to `Right Alt`.

- Stored in config file, no code changes needed to rebind
- `Right Alt` chosen as default: rarely used on Linux, easy to hold, non-destructive if accidentally pressed

---

### Hotkey capture
**`evdev`** as primary, **`pynput`** as fallback.

- `evdev` reads directly from `/dev/input` — works on X11, Wayland, and TTY regardless of compositor
- User must be in the `input` group (`users.extraGroups = ["input"]` on NixOS)
- App checks group membership at startup and prints a clear error if missing
- `pynput` fallback for environments where `evdev` access is unavailable

---

### Audio recording
**`sounddevice`** (PortAudio backend).

- Clean numpy-based API, actively maintained
- Handles ALSA / PulseAudio / PipeWire transparently
- Audio buffered in-memory as numpy array while key is held, passed directly to faster-whisper on release — no temp files

---

### Whisper backend
**`faster-whisper`**, default model **`small`**.

- 2–4x faster than original openai-whisper on CPU, identical accuracy
- Clean Python API, multilingual out of the box
- CUDA support available when GPU is added later — no migration needed
- Model size is configurable

---

### Language detection
**Auto-detect per dictation**, with a configurable fallback language.

- faster-whisper's language detection adds minimal overhead
- Supports seamless mid-session language switching
- If detection confidence is low, falls back to configured default

---

### Text insertion
**Clipboard + auto-paste**, with display server auto-detection.

| Display server | Clipboard tool | Paste simulation |
|---|---|---|
| X11 | `xclip` | `xdotool key ctrl+v` |
| Wayland | `wl-copy` | `ydotool key ctrl+v` |

Detection via `$WAYLAND_DISPLAY` vs `$DISPLAY` environment variables at runtime.

---

### Post-processing
Applied to transcribed text before pasting:

| Feature | Default | Configurable |
|---|---|---|
| Punctuation commands (`"comma"` → `,`, `"period"` → `.`, `"new line"` → `\n`) | On | Yes |
| Auto-capitalize first letter | On | Yes |
| Filler word stripping (`uh`, `um`, etc.) | Off | Yes |
| Custom substitution rules | — | Yes (defined in config) |

---

### UI — Recording indicator
**Small floating overlay**, fixed screen corner (default: bottom-right).

- Appears only while recording
- Configurable corner: `bottom-right`, `bottom-left`, `top-right`, `top-left`
- Implemented as a small always-on-top window (tkinter or similar)
- Works on X11 and Wayland

---

### Audio feedback
**Configurable, defaulting to off (visual-only).**

- Toggle in config
- If enabled: simple system beep or small bundled wav files on record start/stop

---

### Run modes
Two modes, same binary:

1. **Foreground** (default) — runs in terminal, easy to debug, logs to stdout
2. **Daemon** (`--daemon` flag) — installs and enables a systemd user service

NixOS users also get a native module:
```nix
services.voxy.enable = true;
```

---

### File layout (XDG)

```
~/.config/voxy/config.toml       # user configuration
~/.cache/voxy/models/            # downloaded Whisper models
~/.local/share/voxy/voxy.log     # logs
```

---

### Configuration format
**TOML** — human-readable, supports comments, `tomllib` built into Python 3.11+.

Example `config.toml`:
```toml
[hotkey]
key = "right_alt"

[model]
size = "small"
language = "auto"
fallback_language = "en"

[insertion]
method = "auto"  # auto | x11 | wayland

[post_processing]
punctuation_commands = true
auto_capitalize = true
strip_fillers = false
fillers = ["uh", "um", "hmm"]

[post_processing.substitutions]
"new line" = "\n"
"new paragraph" = "\n\n"
"comma" = ","
"period" = "."
"question mark" = "?"
"exclamation mark" = "!"
"colon" = ":"
"semicolon" = ";"

[ui]
overlay = true
overlay_corner = "bottom-right"
audio_feedback = false

[logging]
level = "info"
```

---

## Tech Stack

| Component | Library / Tool |
|---|---|
| Language | Python 3.11+ |
| Transcription | `faster-whisper` |
| Audio capture | `sounddevice` |
| Hotkey capture | `evdev` + `pynput` fallback |
| X11 clipboard | `xclip` |
| X11 paste | `xdotool` |
| Wayland clipboard | `wl-clipboard` (`wl-copy`) |
| Wayland paste | `ydotool` |
| Overlay UI | `tkinter` |
| Config parsing | `tomllib` (stdlib) / `tomli` fallback |
| Packaging | Nix flake |

---

## Build Order

1. `flake.nix` — Nix packaging, dev shell, all dependencies
2. Core audio + transcription loop — record → transcribe → output text
3. Hotkey capture — evdev push-to-talk
4. Text insertion — clipboard + paste, X11/Wayland
5. Overlay UI — floating recording indicator
6. Post-processing — punctuation commands, capitalize, substitutions
7. Daemon mode — systemd user service + `--daemon` flag
8. NixOS module — `services.voxy`
