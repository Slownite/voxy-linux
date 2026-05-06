# voxy 🎙️

> **Hold. Speak. Release. Done.**

Local, offline voice dictation for Linux — text appears instantly in whatever window is active. No cloud. No subscription. No audio ever leaves your machine.

Built on [faster-whisper](https://github.com/SYSTRAN/faster-whisper) (2–4× faster than openai-whisper on CPU, same accuracy). Supports Wayland and X11 via optional display-server extras. Ships as a Nix flake.

---

## Installation

### uvx (try without installing)

```bash
uvx --with "voxy-linux[wayland]" voxy-linux   # Wayland
uvx --with "voxy-linux[x11]"     voxy-linux   # X11
```

### pipx (persistent isolated install)

```bash
pipx install "voxy-linux[wayland]"   # Wayland
pipx install "voxy-linux[x11]"       # X11
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

**Text insertion + cursor overlay** (install the set that matches your display server)

| Display server | System packages | Python extra |
|---|---|---|
| Wayland | `wl-clipboard` + `ydotool` + `gtk4` + `gtk4-layer-shell` | `[wayland]` |
| X11 | `xclip` + `xdotool` | `[x11]` |

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
key = "right_alt"              # evdev key name

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

### Hyprland plugin (optional)

The cursor overlay normally just draws a green frame around the pointer.
To make the overlay also **mirror the live system cursor shape** (I-beam
in text fields, hand on links, resize cursors at window edges, …), voxy
ships a small Hyprland plugin in
[`hyprland-plugin/cursor-shape-emit/`](hyprland-plugin/cursor-shape-emit/).
It hooks `CCursorManager::setCursorFromName` and
`CInputManager::onMouseMoved` and re-emits them as Hyprland IPC events
(`cursorshape>>name`, `cursormove>>x,y`) that voxy reads over `socket2`.

**When it's used.** Only on Hyprland, only when `[ui] cursor_overlay =
true`. On every startup `build_cursor_overlay()` calls
`_ensure_cursor_plugin()`
([`src/voxy/cursor_overlay.py`](src/voxy/cursor_overlay.py)), which:

1. Looks for `~/.local/share/hyprland/plugins/cursor-shape-emit.so`.
2. Skips if the file is missing (debug log, no error) — the overlay
   still works, just without shape-aware cursor outlines.
3. Otherwise asks `hyprctl plugin list` whether it's already loaded;
   if not, runs `hyprctl plugin load <path>`.

There is **no auto-build**: `pip` / `pipx` / `uvx` and the AUR package
all install only the Python code, so until you build and install the
`.so` yourself voxy runs without it.

**How to install it.** You need the repo checked out and Hyprland's
development headers on the system (`pacman -S hyprland` on Arch —
adjust for your distro):

```bash
git clone https://github.com/samanddima/voxy-linux
cd voxy-linux/hyprland-plugin/cursor-shape-emit
make           # produces cursor-shape-emit.so
make install   # copies to ~/.local/share/hyprland/plugins/
```

The next time voxy starts (or restart the user service:
`systemctl --user restart voxy`) it will load the plugin. Verify with
`hyprctl plugin list` — `cursor-shape-emit` should appear.

> **NixOS users:** the Nix flake doesn't build this plugin and
> `hyprctl plugin load` against a hand-built `.so` isn't the right
> workflow on NixOS. Use Hyprland's own plugin support
> ([wiki.hyprland.org/Plugins/Using-Plugins](https://wiki.hyprland.org/Plugins/Using-Plugins/))
> to package and load `cursor-shape-emit` from `hyprland-plugin/cursor-shape-emit/`.

**To uninstall:** `hyprctl plugin unload
~/.local/share/hyprland/plugins/cursor-shape-emit.so` and delete the
file. voxy will fall back to the plain green frame on the next launch.

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

**`hotkey`** — evdev key name (e.g. `right_alt`, `right_ctrl`, `f13`)

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
uv sync --extra dev --extra wayland   # Wayland
uv sync --extra dev --extra x11       # X11
uv run python -m voxy
uv run pytest
uv run mypy --strict src/
uv build
```

### Nix dev shells

```bash
nix develop                              # Wayland shell (default)
nix develop .#x11                        # X11 shell
nix develop .#cuda                       # Wayland + CUDA shell
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
