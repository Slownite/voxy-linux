Hyprland plugin
===============

``hyprland-plugin/cursor-shape-emit/`` is the C++ Hyprland plugin that
draws voxy's cursor-anchored outline directly inside the compositor and
emits cursor-shape change events on the Hyprland IPC socket.

This page is the high-level overview. The full developer guide
(including the rendering contract with Hyprland, build/test commands, and
upgrade procedure) is the plugin's own README, included verbatim below.

.. toctree::
   :hidden:

   render-contract
   test-strategy

.. include:: ../../hyprland-plugin/cursor-shape-emit/README.md
   :parser: myst_parser.sphinx_
