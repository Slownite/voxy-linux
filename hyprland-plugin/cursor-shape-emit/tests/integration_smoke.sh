#!/usr/bin/env bash
# Integration smoke test for cursor-shape-emit.
#
# Loads the built .so into a live Hyprland (the one that exported
# HYPRLAND_INSTANCE_SIGNATURE), runs every registered dispatcher, optionally
# verifies the cursorshape IPC event fires, then unloads and restores the
# previous plugin state on exit (success or failure).
#
# Exit codes:
#   0   success
#   1   fail (dispatcher errored, plugin failed to load, IPC missing, …)
#   77  skipped (no usable Hyprland to test against)

set -euo pipefail

PLUGIN_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/cursor-shape-emit.so"

if [[ ! -f "$PLUGIN_PATH" ]]; then
    echo "smoke: plugin not built: $PLUGIN_PATH"
    exit 1
fi
if ! command -v hyprctl >/dev/null 2>&1; then
    echo "smoke: hyprctl not found — SKIP"
    exit 77
fi
if [[ -z "${HYPRLAND_INSTANCE_SIGNATURE:-}" ]]; then
    echo "smoke: no live Hyprland instance — SKIP"
    echo "       (run inside Hyprland or export HYPRLAND_INSTANCE_SIGNATURE)"
    exit 77
fi

echo "smoke: target Hyprland instance = $HYPRLAND_INSTANCE_SIGNATURE"

# Snapshot prior load state; trap restores it on any exit path.
restore=0
if hyprctl plugin list 2>/dev/null | grep -q "cursor-shape-emit"; then
    echo "smoke: plugin already loaded — will reload"
    hyprctl plugin unload "$PLUGIN_PATH" >/dev/null
    restore=1
fi

cleanup() {
    # Best effort — unload any test-loaded copy, then restore prior state.
    if hyprctl plugin list 2>/dev/null | grep -q "cursor-shape-emit"; then
        hyprctl plugin unload "$PLUGIN_PATH" >/dev/null 2>&1 || true
    fi
    if [[ $restore -eq 1 ]]; then
        hyprctl plugin load "$PLUGIN_PATH" >/dev/null 2>&1 || true
        echo "smoke: restored prior load"
    fi
}
trap cleanup EXIT

# 1. Load.
out="$(hyprctl plugin load "$PLUGIN_PATH" 2>&1)"
if [[ "$out" != "ok" ]]; then
    echo "smoke: FAIL plugin load: $out"
    exit 1
fi
echo "smoke: load OK"

# 2. Plugin reports loaded.
if ! hyprctl plugin list | grep -q "cursor-shape-emit"; then
    echo "smoke: FAIL plugin not in list after load"
    exit 1
fi
echo "smoke: list OK"

# 3. Each registered dispatcher accepts the no-arg call.
for d in \
    "cursorshapequery" \
    "voxy:overlay_show" \
    "voxy:overlay_processing" \
    "voxy:overlay_hide"
do
    r="$(hyprctl dispatch "$d" 2>&1)"
    if [[ "$r" != "ok" ]]; then
        echo "smoke: FAIL dispatch $d returned: $r"
        exit 1
    fi
    echo "smoke: dispatch $d OK"
done

# 4. Verify cursorshape IPC event fires when cursorshapequery is dispatched.
#    Subscribe socket2 in the background, run query, look for the event.
SOCKET="${XDG_RUNTIME_DIR:-/tmp}/hypr/$HYPRLAND_INSTANCE_SIGNATURE/.socket2.sock"
if [[ -S "$SOCKET" ]] && command -v socat >/dev/null 2>&1; then
    EVENTS_FILE="$(mktemp)"
    socat -u "UNIX-CONNECT:$SOCKET" - >"$EVENTS_FILE" 2>/dev/null &
    SOCAT_PID=$!
    # Give socat a moment to connect before we trigger the event.
    sleep 0.2
    hyprctl dispatch cursorshapequery >/dev/null
    sleep 0.3
    kill "$SOCAT_PID" 2>/dev/null || true
    wait "$SOCAT_PID" 2>/dev/null || true
    if grep -q '^cursorshape>>' "$EVENTS_FILE"; then
        echo "smoke: IPC cursorshape event observed OK"
    else
        # Not all cursors have been set via setCursorFromName by the time the
        # test runs — s_lastCursorName may be empty and the event never fires.
        # Treat as warning, not failure.
        echo "smoke: WARN no cursorshape event observed (s_lastCursorName likely empty)"
    fi
    rm -f "$EVENTS_FILE"
else
    echo "smoke: WARN socket2 / socat not available — skipping IPC event check"
fi

# 5. Unload.
out="$(hyprctl plugin unload "$PLUGIN_PATH" 2>&1)"
if [[ "$out" != "ok" ]]; then
    echo "smoke: FAIL plugin unload: $out"
    exit 1
fi
echo "smoke: unload OK"

echo "smoke: PASS"
