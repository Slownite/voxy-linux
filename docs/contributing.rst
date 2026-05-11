Contributing
============

Patches, bug reports, and ideas are welcome. The codebase is small;
it's a friendly entry into Linux desktop hacking.

Where to start
--------------

- **Bug reports**: open a `GitHub issue
  <https://github.com/samanddima/voxy-linux/issues>`_ — include distro,
  display server, ``voxy --version``, and the output of
  ``voxy`` run in the foreground.
- **Ideas / discussion**: the `Discussions tab
  <https://github.com/samanddima/voxy-linux/discussions>`_ is the
  best place to float a feature before writing code.
- **Good first changes**:

  - Add a translation profile under ``[postprocess.profiles]``.
  - Improve a troubleshooting entry on this site.
  - Smooth out a rough edge in the first-run wizard.
  - Add a test case for a module under ``tests/``.

Local development
-----------------

.. code-block:: bash

   git clone https://github.com/samanddima/voxy-linux
   cd voxy-linux
   uv sync                            # creates .venv, installs python deps
   uv run voxy                        # iterate (foreground, Ctrl+C to stop)

For the Hyprland plugin:

.. code-block:: bash

   cd hyprland-plugin/cursor-shape-emit
   just check                         # unit + ASAN + smoke + shellcheck
   just reload                        # rebuild + reload into running Hyprland

Conventions
-----------

- **Python**: 3.11+, typed strictly (``mypy --strict`` passes). Format
  with ``ruff format``; lint with ``ruff check``.
- **C++** *(plugin only)*: C++26, no exceptions, prefer ``SP<>`` /
  ``UP<>`` over raw pointers.
- **Commit messages**: Conventional Commits
  (``feat:``, ``fix:``, ``docs:``, ``refactor:``, ``chore:``).
  Subject line ≤ 70 chars; body explains the *why*.
- **Pull requests**: keep them focused. Refactors that aren't strictly
  needed for a feature go in their own PR.

ADRs
----

Decisions that are *expensive to reverse* (display-server back-end,
plugin ABI surface, dependency you can't yank without re-architecting)
get an :doc:`Architecture Decision Record <decisions/index>` in
``docs/decisions/``. Use the next available number.

Building the docs
-----------------

.. code-block:: bash

   just docs                # build + open in browser
   just docs-serve          # live-reload on http://localhost:8080
   just docs-strict         # CI build, fails on any warning

The Hyprland plugin's developer README is the canonical source; the
docs page under ``docs/hyprland-plugin/`` ``include::``-s it via MyST so
there is no duplication.

Releases
--------

Maintainers tag in the ``YYYY.M.D.N`` format (see ``CLAUDE.md``). The
``release.yml`` GitHub Action builds the PyPI wheel and the AUR
``PKGBUILD`` candidate on tag push.

Code of conduct
---------------

Be kind, be patient, focus on the work. No specific COC document yet —
the project is small enough that good faith covers it.
