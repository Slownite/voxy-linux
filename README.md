# voxy 🎙️

> **Hold. Speak. Release. Done.**

Local, offline voice dictation for Linux — text appears instantly in whatever window is active. No cloud. No subscription. No audio ever leaves your machine.

Built on [faster-whisper](https://github.com/SYSTRAN/faster-whisper) (2–4× faster than openai-whisper on CPU, same accuracy). Works on X11 and Wayland. Ships as a Nix flake.

---

## Installation

### uvx (try without installing)

```bash
uvx voxy-linux
```

### pipx (persistent isolated install)

```bash
pipx install voxy-linux
```

### AUR (Arch / Manjaro)

```bash
yay -S voxy-linux
```

### NixOS

See the [NixOS](#nixos) section below.

---

## Prerequisites

Before installing via `pip` / `pipx` / `uvx`, install the required system packages.

**Audio** (required)

| Distro | Command |
|---|---|
| Debian / Ubuntu | `sudo apt install libportaudio2` |
| Fedora | `sudo dnf install portaudio` |
| Arch | `sudo pacman -S portaudio` |

**Text insertion** (install the set that matches your display server)

| Display server | Packages |
|---|---|
| X11 | `xclip` + `xdotool` |
| Wayland | `wl-clipboard` + `ydotool` |

**Cursor overlay** (optional, Hyprland only — see [Cursor overlay](#cursor-overlay))

| Distro | Command |
|---|---|
| Arch | `sudo pacman -S gtk4 gtk4-layer-shell python-gobject python-cairo` |

Then install voxy with the extra: `pipx install 'voxy-linux[cursor-overlay]'`.

> **macOS / Windows:** voxy is Linux-only. The package will install but will not run on other platforms.

---

## How it works

1. Hold the hotkey (default: **Right Alt**)
2. Speak
3. Release — transcribed text is pasted into the active window

That's it.

A small overlay appears in a configurable screen corner:

- **REC** (red) — microphone is active
- **PROCESSING** (amber) — transcribing
- Overlay disappears once text is inserted

On Hyprland, voxy can additionally draw a green frame and status pill
**anchored to the mouse cursor** while the hotkey is held. See
[Cursor overlay](#cursor-overlay).

A tray icon (StatusNotifierItem — works in waybar, KDE, GNOME with the
right extension) mirrors the same three states and offers a right-click
**Quit** entry. A short toast notification is shown each time a
transcript lands in your clipboard. Both are toggleable in `config.toml`.

---

## Quick start

```bash
voxy                        # run in foreground
voxy --daemon install       # install as a systemd user service
voxy --daemon remove        # stop and remove the service
voxy --daemon status        # check service status
```

On first run, voxy prompts for a Whisper model size (default: **auto**,
which picks `tiny`/`base`/`small` based on your CPU's core count and
AVX/VNNI flags, or `small` on GPU). The default config is written to
`~/.config/voxy/config.toml` and the model is downloaded to
`~/.cache/voxy/models/` with a tqdm progress bar. Subsequent runs skip
the prompt and reuse the cached model.

> Set `HF_TOKEN` (or run `huggingface-cli login`) to avoid Hugging Face
> rate limits during the download.

---

## Configuration

`~/.config/voxy/config.toml` — created with defaults on first run, fully commented.

```toml
[hotkey]
key = "right_alt"              # evdev/pynput key name

[model]
size = "auto"                  # auto | tiny | base | small | medium | large-v3
language = "auto"              # auto-detect per utterance, or a BCP-47 code
fallback_language = "en"

[insertion]
method = "auto"                # auto | x11 | wayland

[post_processing]
punctuation_commands = true    # say "comma" → ,  "period" → .  "new line" → ↵
auto_capitalize = true
strip_fillers = false
fillers = ["uh", "um", "hmm"]

[post_processing.substitutions]
"new line"      = "\n"
"new paragraph" = "\n\n"
"comma"         = ","
"period"        = "."

[ui]
overlay = true
overlay_corner = "bottom-right"    # top-left | top-right | bottom-left | bottom-right
audio_feedback = false
notify = true                      # toast notification on each transcript
tray = true                        # StatusNotifierItem tray icon
cursor_overlay = true              # green frame around cursor (Hyprland only)

[logging]
level = "info"
```

**GPU acceleration:** voxy auto-detects CUDA by default. To override, set `device` under `[model]`:

```toml
[model]
device = "auto"   # auto (default) | cpu | cuda
```

- `auto` — uses the GPU if one is found, falls back to CPU silently
- `cuda` — requires a GPU; logs a warning and falls back to CPU if none is present
- `cpu` — always uses CPU regardless of available hardware

On GPU, the compute type is selected automatically: `int8_float16` (Turing+), `float16` (Pascal+), or `float32` fallback. The selected device and compute type are logged at startup.

---

## Cursor overlay

When enabled (`[ui] cursor_overlay = true`), voxy draws a green frame
around the mouse cursor plus a small status rectangle to its
bottom-right while the push-to-talk key is held and during
transcription. The corner overlay is suppressed on Wayland when the
cursor overlay is active.

- **Hyprland (Wayland):** GTK4 + `gtk4-layer-shell` layer surface; cursor
  position streamed over the Hyprland IPC socket. Requires the
  `cursor-overlay` extra (`pygobject` + `pycairo`) and the system
  packages listed in [Prerequisites](#prerequisites).
- **X11:** Tk override-redirect strips with XShape click-through;
  pointer position via `pynput`.
- **Other Wayland compositors** (Sway, KDE, GNOME): no-op; falls back to
  the corner overlay.

See [docs/adr/0001-cursor-overlay.md](docs/adr/0001-cursor-overlay.md)
for the design rationale.

---

**Terminal paste:** when a terminal emulator is the active window (alacritty, kitty, ghostty, gnome-terminal, konsole), voxy automatically uses Ctrl+Shift+V instead of Ctrl+V. No configuration needed.

**Config path override:** set `VOXY_CONFIG=/path/to/config.toml` to point voxy at a specific file. This takes priority over `~/.config/voxy/config.toml`.

---

## NixOS

### Add to your flake

```nix
# flake.nix
{
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    voxy.url    = "github:samanddima/voxy-linux";
  };

  outputs = { nixpkgs, voxy, ... }: {
    nixosConfigurations.my-host = nixpkgs.lib.nixosSystem {
      modules = [
        voxy.nixosModules.voxy
        ./configuration.nix
      ];
    };
  };
}
```

### Minimal config

```nix
# configuration.nix
{
  services.voxy.enable = true;

  # Required: the voxy user needs access to /dev/input for hotkey capture.
  users.users.your-username.extraGroups = [ "input" ];
}
```

### All options

| Option | Type | Default | Description |
|---|---|---|---|
| `services.voxy.enable` | `bool` | `false` | Enable voxy |
| `services.voxy.hotkey` | `string` | `"right_alt"` | Push-to-talk key (evdev/pynput name) |
| `services.voxy.modelSize` | `enum` | `"small"` | Whisper model size |
| `services.voxy.overlayCorner` | `enum` | `"bottom-right"` | Recording overlay corner |

**`modelSize`** — `tiny` · `tiny.en` · `base` · `base.en` · `small` · `small.en` · `medium` · `medium.en` · `large-v1` · `large-v2` · `large-v3`

**`overlayCorner`** — `top-left` · `top-right` · `bottom-left` · `bottom-right`

### Example with custom options

```nix
services.voxy = {
  enable      = true;
  hotkey      = "right_ctrl";
  modelSize   = "base";
  overlayCorner = "top-right";
};
```

> **Note:** The NixOS module generates a `config.toml` from your declared options and passes it to the service via `VOXY_CONFIG`. `VOXY_CONFIG` takes priority over `~/.config/voxy/config.toml` — so the system-level declaration wins unless you run voxy manually without the env var set.

---

## Development

### Setup

```bash
git clone https://github.com/samanddima/voxy-linux
cd voxy-linux
just setup          # install deps + dev extras into .venv
```

### Common tasks

```bash
just run            # run from source
just test           # run test suite
just typecheck      # mypy --strict
just build          # build wheel → dist/
just install        # build + pipx install
just clean          # remove dist/ and .venv/
```

### Repo stats

```bash
just count_lines            # total Python LOC
just top_files              # top 20 files by size
just modules                # list all modules
just test_ratio             # test-to-source ratio
just todos                  # TODO/FIXME markers
just churn                  # commit hotspots
just deps                   # dependency counts
```

### Without just (manual)

```bash
uv sync --extra dev
uv run python -m voxy
uv run pytest
uv run mypy --strict src/
uv build
```

### NixOS dev shell

```bash
nix develop                              # enter shell with Python + all deps
nix develop --command pytest             # run tests
nix develop --command mypy --strict src/ # type check
```

---

## Troubleshooting

**Overlay not visible when running as a service**

The service starts after `graphical-session.target`, but display auth (`XAUTHORITY`) may not be ready immediately. If `journalctl --user -u voxy.service` shows "overlay disabled", add a short delay:

```nix
# configuration.nix
systemd.user.services.voxy.serviceConfig.ExecStartPre = "/bin/sleep 2";
```

**Indicator stays amber / nothing is pasted**

Make sure you have rebuilt after any `flake.nix` change:

```bash
sudo nixos-rebuild switch
```

Or run from the dev shell directly — the installed package won't pick up source changes:

```bash
nix develop --command python -m voxy
```

**Hotkey not captured**

Your user must be in the `input` group:

```nix
users.users.your-username.extraGroups = [ "input" ];
```

Apply with `sudo nixos-rebuild switch`, then log out and back in.

---

## Credits

UX reference: [WisprFlow](https://wisprflow.ai/) — voxy is the Linux-native, offline, open-source answer to it.
