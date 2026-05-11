Changelog
=========

Releases follow the date-based ``YYYY.M.D.N`` tag format. The
authoritative list of changes is the
`GitHub Releases page
<https://github.com/samanddima/voxy-linux/releases>`_.

Recent highlights
-----------------

- **In-compositor cursor outline (Hyprland).** A C++ plugin draws the
  recording-state outline inside Hyprland's render pass, eliminating
  the one-frame trail of a client-side overlay. See
  :doc:`hyprland-plugin/index`.
- **First-run model prompt.** On first launch, voxy asks which Whisper
  size to download and pre-fetches it before entering the hotkey loop.
- **CPU-flag-aware auto model selection.** ``model.size = "auto"``
  picks ``small`` on GPU or AVX2+VNNI, ``base`` on AVX2, ``tiny``
  otherwise.
- **Tray icon (StatusNotifierItem).** State mirrors the corner overlay;
  right-click for **Quit**. Compatible with waybar, KDE Plasma, GNOME
  + AppIndicator extension.
- **Terminal-aware paste.** When the focused window is a known
  terminal emulator, voxy substitutes ``Ctrl+Shift+V`` for ``Ctrl+V``
  so paste actually lands.
