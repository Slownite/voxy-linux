# voxy 🎙️

> **Hold. Speak. Release. Done.**

Local, offline voice dictation for Linux — text appears instantly in whatever window is active. No cloud. No subscription. No audio ever leaves your machine.

Built on [faster-whisper](https://github.com/SYSTRAN/faster-whisper) (2–4× faster than openai-whisper on CPU, same accuracy). Works on X11 and Wayland. Ships as a Nix flake.

---

## How it works

1. Hold the hotkey (default: **Right Alt**)
2. Speak
3. Release — transcribed text is pasted into the active window

That's it.

---

## Quick start

```bash
voxy                        # run in foreground
voxy --daemon install       # install as a systemd user service
voxy --daemon remove        # stop and remove the service
voxy --daemon status        # check service status
```

On first run a default config is written to `~/.config/voxy/config.toml` and the Whisper model is downloaded to `~/.cache/voxy/models/`.

---

## Configuration

`~/.config/voxy/config.toml` — created with defaults on first run, fully commented.

```toml
[hotkey]
key = "right_alt"              # evdev/pynput key name

[model]
size = "small"                 # tiny | base | small | medium | large-v3
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

[logging]
level = "info"
```

---

## NixOS

### Add to your flake

```nix
# flake.nix
{
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    voxy.url    = "github:Slownite/voxy-linux";
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

> **Note:** The NixOS module generates a `config.toml` from your declared options and passes it to the service via `VOXY_CONFIG`. If you also have a `~/.config/voxy/config.toml`, that file takes priority — giving you a per-user escape hatch over system-level defaults.

---

## Development

```bash
nix develop        # enter the dev shell (Python + all deps)
pytest             # run the test suite
mypy src/          # strict type check
```

---

## Credits

UX reference: [WisprFlow](https://wisprflow.ai/) — voxy is the Linux-native, offline, open-source answer to it.
