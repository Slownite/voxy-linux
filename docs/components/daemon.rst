daemon.py
=========

systemd-user-service manager. Wraps ``systemctl --user`` so you can
install voxy as a session-scoped service with one command.

Source: ``src/voxy/daemon.py``.

CLI surface
-----------

.. code-block:: bash

   voxy --daemon install        # write the unit, daemon-reload, enable --now
   voxy --daemon status         # systemctl --user status voxy.service
   voxy --daemon remove         # disable --now + delete the unit file

The unit file is written to
``~/.config/systemd/user/voxy.service`` and launches voxy in the
user's graphical session (after ``graphical-session.target``).

What it doesn't do
------------------

- **No PID file.** Foreground voxy isn't tracked by anything outside
  ``systemd-user``. Stop a foreground process with ``Ctrl+C``.
- **No ``--stop`` flag.** Use ``voxy --daemon remove`` (for the
  service) or kill the foreground process (for an ad-hoc run).
- **No multi-instance check.** Running ``voxy`` twice on the same
  session will compete for the hotkey grab. Don't.

Logs
----

.. code-block:: bash

   journalctl --user -u voxy.service          # last 100 lines
   journalctl --user -u voxy.service -f       # follow
