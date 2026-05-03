#!/usr/bin/env bash
# Prerequisites for voxy on Arch Linux.
# Run once before installing voxy. Requires sudo.
set -euo pipefail

# --- system packages ---

PKGS=()

# audio capture
if ! pacman -Qi portaudio &>/dev/null; then
    PKGS+=(portaudio)
fi

# wayland text insertion
if [[ -n "${WAYLAND_DISPLAY:-}" ]] || [[ "${XDG_SESSION_TYPE:-}" == "wayland" ]]; then
    pacman -Qi wl-clipboard &>/dev/null || PKGS+=(wl-clipboard)
    pacman -Qi ydotool      &>/dev/null || PKGS+=(ydotool)
fi

# wayland cursor overlay (optional, opt-in via [ui] cursor_overlay)
if [[ -n "${WAYLAND_DISPLAY:-}" ]] || [[ "${XDG_SESSION_TYPE:-}" == "wayland" ]]; then
    pacman -Qi gtk4               &>/dev/null || PKGS+=(gtk4)
    pacman -Qi gtk4-layer-shell   &>/dev/null || PKGS+=(gtk4-layer-shell)
    pacman -Qi python-gobject     &>/dev/null || PKGS+=(python-gobject)
    pacman -Qi python-cairo       &>/dev/null || PKGS+=(python-cairo)
fi

# x11 text insertion
if [[ -n "${DISPLAY:-}" ]] || [[ "${XDG_SESSION_TYPE:-}" == "x11" ]]; then
    pacman -Qi xclip   &>/dev/null || PKGS+=(xclip)
    pacman -Qi xdotool &>/dev/null || PKGS+=(xdotool)
fi

if [[ ${#PKGS[@]} -gt 0 ]]; then
    echo "Installing: ${PKGS[*]}"
    sudo pacman -S --needed "${PKGS[@]}"
else
    echo "All system packages already installed."
fi

# --- ydotoold daemon (Wayland only) ---

if pacman -Qi ydotool &>/dev/null; then
    if ! systemctl --user is-enabled --quiet ydotool 2>/dev/null; then
        echo "Enabling ydotool user service..."
        systemctl --user enable --now ydotool
    else
        echo "ydotool user service already enabled."
    fi
fi

# --- cublas .so.12 shim (faster-whisper needs .12, Arch ships cuda 13) ---

CUBLAS_LIB=/opt/cuda/targets/x86_64-linux/lib
if [[ -f "$CUBLAS_LIB/libcublas.so.13" ]] && [[ ! -e "$CUBLAS_LIB/libcublas.so.12" ]]; then
    echo "Creating libcublas.so.12 symlink for faster-whisper compatibility..."
    sudo ln -s "$CUBLAS_LIB/libcublas.so.13"   "$CUBLAS_LIB/libcublas.so.12"
    sudo ln -s "$CUBLAS_LIB/libcublasLt.so.13" "$CUBLAS_LIB/libcublasLt.so.12"
    sudo ldconfig
else
    [[ -e "$CUBLAS_LIB/libcublas.so.12" ]] && echo "libcublas.so.12 already present."
fi

# --- input group (needed for evdev hotkey capture) ---

if getent group input &>/dev/null; then
    if ! id -nG "$USER" | grep -qw input; then
        echo "Adding $USER to input group..."
        sudo usermod -aG input "$USER"
        echo "WARNING: Log out and back in for group membership to take effect."
    else
        echo "$USER already in input group."
    fi
fi

echo ""
echo "Setup complete. Install voxy:"
echo "  pipx install voxy-linux"
echo "  # or: uvx voxy-linux"
