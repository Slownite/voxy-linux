voxy
====

**Hold. Speak. Release. Done.**

Local, offline voice dictation for Linux — text appears instantly in
whatever window you're using. No cloud. No subscription. No audio ever
leaves your machine.

.. grid:: 1 2 2 2
   :gutter: 3

   .. grid-item-card:: Get started
      :link: quickstart
      :link-type: doc

      Install and start dictating in under five minutes.

   .. grid-item-card:: Usage
      :link: usage
      :link-type: doc

      The push-to-talk workflow, indicators, tray icon, and tips for
      everyday dictation.

   .. grid-item-card:: Configuration
      :link: configuration
      :link-type: doc

      Hotkey, microphone, Whisper model, overlays, post-processing —
      every knob in ``config.toml``.

   .. grid-item-card:: How it works
      :link: how-it-works
      :link-type: doc

      Plain-English tour of what happens between hotkey press and
      pasted text.

Built on `faster-whisper <https://github.com/SYSTRAN/faster-whisper>`_
(2–4× faster than openai-whisper on CPU, same accuracy). Works on X11,
generic Wayland, and Hyprland. Ships as a PyPI package, an AUR package,
and a Nix flake.

.. toctree::
   :hidden:
   :caption: Get started

   quickstart
   installation
   usage
   configuration
   troubleshooting

.. toctree::
   :hidden:
   :caption: Understand

   how-it-works
   privacy

.. toctree::
   :hidden:
   :caption: Under the hood

   architecture/index
   components/index
   hyprland-plugin/index

.. toctree::
   :hidden:
   :caption: Project

   decisions/index
   contributing
   changelog
