"""Tray — StatusNotifierItem icon for voxy via dbus-next."""

import asyncio
import threading
from pathlib import Path
from typing import Callable

from dbus_next import BusType, Variant
from dbus_next.aio import MessageBus
from dbus_next.service import ServiceInterface, dbus_property, method, signal
from dbus_next.constants import PropertyAccess

_WATCHER_BUS: str = "org.kde.StatusNotifierWatcher"
_WATCHER_PATH: str = "/StatusNotifierWatcher"
_ITEM_PATH: str = "/StatusNotifierItem"
_MENU_PATH: str = "/MenuBar"

_ICON_DIR: str = str(Path(__file__).parent / "icons")
_ICON_IDLE: str = "voxy-symbolic"
_ICON_RECORDING: str = "voxy-recording-symbolic"
_ICON_PROCESSING: str = "voxy-processing-symbolic"

_STATE_ICONS: dict[str, str] = {
    "idle": _ICON_IDLE,
    "recording": _ICON_RECORDING,
    "processing": _ICON_PROCESSING,
}


class _StatusNotifierItem(ServiceInterface):
    """Minimal SNI implementing what waybar reads."""

    def __init__(self) -> None:
        super().__init__("org.kde.StatusNotifierItem")
        self._icon_name: str = _ICON_IDLE
        self._tooltip: str = "voxy — idle"

    def set_icon(self, name: str) -> None:
        self._icon_name = name
        self.NewIcon()

    def set_tooltip(self, text: str) -> None:
        self._tooltip = text
        self.NewToolTip()

    @dbus_property(access=PropertyAccess.READ)
    def Category(self) -> "s":  # type: ignore[name-defined]  # noqa: F722
        return "ApplicationStatus"

    @dbus_property(access=PropertyAccess.READ)
    def Id(self) -> "s":  # type: ignore[name-defined]  # noqa: F722
        return "voxy"

    @dbus_property(access=PropertyAccess.READ)
    def Title(self) -> "s":  # type: ignore[name-defined]  # noqa: F722
        return "voxy"

    @dbus_property(access=PropertyAccess.READ)
    def Status(self) -> "s":  # type: ignore[name-defined]  # noqa: F722
        return "Active"

    @dbus_property(access=PropertyAccess.READ)
    def WindowId(self) -> "i":  # type: ignore[name-defined]  # noqa: F722
        return 0

    @dbus_property(access=PropertyAccess.READ)
    def IconName(self) -> "s":  # type: ignore[name-defined]  # noqa: F722
        return self._icon_name

    @dbus_property(access=PropertyAccess.READ)
    def IconThemePath(self) -> "s":  # type: ignore[name-defined]  # noqa: F722
        return _ICON_DIR

    @dbus_property(access=PropertyAccess.READ)
    def AttentionIconName(self) -> "s":  # type: ignore[name-defined]  # noqa: F722
        return ""

    @dbus_property(access=PropertyAccess.READ)
    def OverlayIconName(self) -> "s":  # type: ignore[name-defined]  # noqa: F722
        return ""

    @dbus_property(access=PropertyAccess.READ)
    def ToolTip(self) -> "(sa(iiay)ss)":  # type: ignore[name-defined]  # noqa: F722
        return ["", [], "voxy", self._tooltip]

    @dbus_property(access=PropertyAccess.READ)
    def ItemIsMenu(self) -> "b":  # type: ignore[name-defined]  # noqa: F722
        return False

    @dbus_property(access=PropertyAccess.READ)
    def Menu(self) -> "o":  # type: ignore[name-defined]  # noqa: F722
        return _MENU_PATH

    @method()
    def Activate(self, x: "i", y: "i") -> None:  # type: ignore[name-defined]  # noqa: F722, F821
        pass

    @method()
    def SecondaryActivate(self, x: "i", y: "i") -> None:  # type: ignore[name-defined]  # noqa: F722, F821
        pass

    @method()
    def ContextMenu(self, x: "i", y: "i") -> None:  # type: ignore[name-defined]  # noqa: F722, F821
        pass

    @method()
    def Scroll(self, delta: "i", orientation: "s") -> None:  # type: ignore[name-defined]  # noqa: F722, F821
        pass

    @signal()
    def NewIcon(self) -> None:
        pass

    @signal()
    def NewToolTip(self) -> None:
        pass

    @signal()
    def NewStatus(self, status: "s") -> "s":  # type: ignore[name-defined]  # noqa: F722
        return status


class _DBusMenu(ServiceInterface):
    """com.canonical.dbusmenu — context menu shown by waybar/KDE."""

    def __init__(self, items: list[tuple[int, str, Callable[[], None]]]) -> None:
        super().__init__("com.canonical.dbusmenu")
        self._items = items  # (id, label, callback) — id 0 reserved for root
        self._revision = 1

    @dbus_property(access=PropertyAccess.READ)
    def Version(self) -> "u":  # type: ignore[name-defined]  # noqa: F722
        return 3

    @dbus_property(access=PropertyAccess.READ)
    def TextDirection(self) -> "s":  # type: ignore[name-defined]  # noqa: F722
        return "ltr"

    @dbus_property(access=PropertyAccess.READ)
    def Status(self) -> "s":  # type: ignore[name-defined]  # noqa: F722
        return "normal"

    @dbus_property(access=PropertyAccess.READ)
    def IconThemePath(self) -> "as":  # type: ignore[name-defined]  # noqa: F722
        return []

    @method()
    def GetLayout(
        self, parentId: "i", recursionDepth: "i", propertyNames: "as"  # type: ignore[name-defined]  # noqa: F722, F821
    ) -> "u(ia{sv}av)":  # type: ignore[name-defined]  # noqa: F722
        if parentId != 0:
            return [self._revision, [parentId, {}, []]]
        children: list = []
        if recursionDepth != 0:
            for item_id, label, _ in self._items:
                props = {"label": Variant("s", label)}
                children.append(Variant("(ia{sv}av)", [item_id, props, []]))
        root_props = {"children-display": Variant("s", "submenu")}
        return [self._revision, [0, root_props, children]]

    @method()
    def GetGroupProperties(
        self, ids: "ai", propertyNames: "as"  # type: ignore[name-defined]  # noqa: F722, F821
    ) -> "a(ia{sv})":  # type: ignore[name-defined]  # noqa: F722
        out = []
        for item_id, label, _ in self._items:
            if ids and item_id not in ids:
                continue
            props = {
                "label": Variant("s", label),
                "enabled": Variant("b", True),
                "visible": Variant("b", True),
            }
            out.append([item_id, props])
        return out

    @method()
    def GetProperty(self, id: "i", name: "s") -> "v":  # type: ignore[name-defined]  # noqa: F722, F821
        if id == 0 and name == "children-display":
            return Variant("s", "submenu")
        for item_id, label, _ in self._items:
            if item_id != id:
                continue
            if name == "label":
                return Variant("s", label)
            if name in ("enabled", "visible"):
                return Variant("b", True)
        return Variant("s", "")

    @method()
    def Event(
        self, id: "i", eventId: "s", data: "v", timestamp: "u"  # type: ignore[name-defined]  # noqa: F722, F821
    ) -> None:
        if eventId != "clicked":
            return
        for item_id, _, cb in self._items:
            if item_id == id:
                try:
                    cb()
                except Exception:
                    pass
                return

    @method()
    def EventGroup(
        self, events: "a(isvu)"  # type: ignore[name-defined]  # noqa: F722, F821
    ) -> "ai":  # type: ignore[name-defined]  # noqa: F722
        known = {item_id for item_id, _, _ in self._items}
        not_found: list[int] = []
        for ev in events:
            ev_id = ev[0]
            if ev_id not in known:
                not_found.append(ev_id)
                continue
            self.Event(ev_id, ev[1], ev[2], ev[3])
        return not_found

    @method()
    def AboutToShow(self, id: "i") -> "b":  # type: ignore[name-defined]  # noqa: F722, F821
        return False

    @method()
    def AboutToShowGroup(
        self, ids: "ai"  # type: ignore[name-defined]  # noqa: F722, F821
    ) -> "aiai":  # type: ignore[name-defined]  # noqa: F722
        return [[], []]

    @signal()
    def ItemsPropertiesUpdated(
        self,
        updated: "a(ia{sv})",  # type: ignore[name-defined]  # noqa: F722
        removed: "a(ias)",  # type: ignore[name-defined]  # noqa: F722
    ) -> "a(ia{sv})a(ias)":  # type: ignore[name-defined]  # noqa: F722
        return [updated, removed]

    @signal()
    def LayoutUpdated(self, revision: "u", parent: "i") -> "ui":  # type: ignore[name-defined]  # noqa: F722
        return [revision, parent]

    @signal()
    def ItemActivationRequested(self, id: "i", timestamp: "u") -> "iu":  # type: ignore[name-defined]  # noqa: F722
        return [id, timestamp]


class TrayIcon:
    """Tray icon running an SNI service in a dedicated asyncio thread."""

    def __init__(self, on_quit: Callable[[], None]) -> None:
        self._on_quit = on_quit
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._sni: _StatusNotifierItem | None = None
        self._stop_event: asyncio.Event | None = None
        self._ready = threading.Event()
        self.ok: bool = False

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, daemon=True, name="voxy-tray")
        self._thread.start()
        self._ready.wait(timeout=3.0)

    def stop(self) -> None:
        loop = self._loop
        ev = self._stop_event
        if loop is None or ev is None or not loop.is_running():
            return
        loop.call_soon_threadsafe(ev.set)

    def set_state(self, state: str) -> None:
        if not self.ok:
            return
        loop = self._loop
        sni = self._sni
        if loop is None or sni is None:
            return
        icon = _STATE_ICONS.get(state, _ICON_IDLE)
        tooltip = f"voxy — {state}"

        def apply() -> None:
            sni.set_icon(icon)
            sni.set_tooltip(tooltip)

        loop.call_soon_threadsafe(apply)

    def _run(self) -> None:
        try:
            asyncio.run(self._serve())
        except Exception as e:
            print(f"voxy: tray disabled ({e})", flush=True)
        finally:
            self._ready.set()

    async def _serve(self) -> None:
        self._loop = asyncio.get_running_loop()
        self._stop_event = asyncio.Event()
        bus = await MessageBus(bus_type=BusType.SESSION).connect()
        try:
            unique = bus.unique_name

            sni = _StatusNotifierItem()
            menu = _DBusMenu(
                items=[
                    (1, "voxy", lambda: None),
                    (2, "Quit", self._on_quit),
                ]
            )
            bus.export(_ITEM_PATH, sni)
            bus.export(_MENU_PATH, menu)

            # Register with the running StatusNotifierWatcher (waybar/KDE/etc).
            try:
                introspect = await bus.introspect(_WATCHER_BUS, _WATCHER_PATH)
                obj = bus.get_proxy_object(_WATCHER_BUS, _WATCHER_PATH, introspect)
                iface = obj.get_interface(_WATCHER_BUS)
                await iface.call_register_status_notifier_item(unique)
            except Exception as e:
                raise RuntimeError(
                    f"no StatusNotifierWatcher (waybar tray running?): {e}"
                ) from e

            self._sni = sni
            self.ok = True
            self._ready.set()

            await self._stop_event.wait()
        finally:
            bus.disconnect()
