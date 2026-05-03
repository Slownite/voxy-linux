// cursor-shape-emit: Hyprland plugin emitting cursor shape and position events.
//
// Hooks:
//   CCursorManager::setCursorFromName  → "cursorshape>>name"
//   CInputManager::onMouseMoved        → "cursormove>>x,y"
//
// Also registers hyprctl dispatch "cursorshapequery" for clients to request
// the current shape (useful on connect).
//
// Event format:
//   cursorshape>>default
//   cursormove>>123,456

#include <hyprland/src/plugins/PluginAPI.hpp>
#include <hyprland/src/managers/EventManager.hpp>
#include <hyprland/src/managers/input/InputManager.hpp>
#include <hyprland/src/helpers/math/Math.hpp>
#include <string>
#include <format>

static std::string s_lastCursorName;

static CFunctionHook* s_hookShape = nullptr;
static CFunctionHook* s_hookMove  = nullptr;
static HANDLE         s_handle    = nullptr;

using FSetCursorFromName = void (*)(void*, const std::string&);
using FOnMouseMoved      = void (*)(void*, IPointer::SMotionEvent);

static void emitShape(const std::string& name) {
    if (g_pEventManager)
        g_pEventManager->postEvent({.event = "cursorshape", .data = name});
}

static void emitMove(const Vector2D& pos) {
    if (g_pEventManager) {
        std::string data = std::format("{},{}", (int)pos.x, (int)pos.y);
        g_pEventManager->postEvent({.event = "cursormove", .data = data});
    }
}

void hkSetCursorFromName(void* self, const std::string& name) {
    if (name != s_lastCursorName) {
        s_lastCursorName = name;
        emitShape(name);
    }
    (*(FSetCursorFromName)s_hookShape->m_original)(self, name);
}

void hkOnMouseMoved(void* self, IPointer::SMotionEvent ev) {
    (*(FOnMouseMoved)s_hookMove->m_original)(self, ev);
    if (g_pInputManager)
        emitMove(g_pInputManager->getMouseCoordsInternal());
}

static SDispatchResult onCursorShapeQuery(std::string args) {
    if (!s_lastCursorName.empty())
        emitShape(s_lastCursorName);
    return {.success = true};
}

APICALL EXPORT std::string PLUGIN_API_VERSION() {
    return HYPRLAND_API_VERSION;
}

APICALL EXPORT PLUGIN_DESCRIPTION_INFO PLUGIN_INIT(HANDLE handle) {
    s_handle = handle;

    auto shapeMatches = HyprlandAPI::findFunctionsByName(handle, "setCursorFromName");
    void* shapeTarget = nullptr;
    for (auto& m : shapeMatches) {
        if (m.demangled.find("CCursorManager") != std::string::npos) {
            shapeTarget = m.address;
            break;
        }
    }
    if (shapeTarget) {
        s_hookShape = HyprlandAPI::createFunctionHook(handle, shapeTarget, (void*)hkSetCursorFromName);
        if (s_hookShape) s_hookShape->hook();
    }

    auto moveMatches = HyprlandAPI::findFunctionsByName(handle, "onMouseMoved");
    void* moveTarget = nullptr;
    for (auto& m : moveMatches) {
        if (m.demangled.find("CInputManager") != std::string::npos) {
            moveTarget = m.address;
            break;
        }
    }
    if (moveTarget) {
        s_hookMove = HyprlandAPI::createFunctionHook(handle, moveTarget, (void*)hkOnMouseMoved);
        if (s_hookMove) s_hookMove->hook();
    }

    HyprlandAPI::addDispatcherV2(handle, "cursorshapequery", onCursorShapeQuery);

    return {"cursor-shape-emit", "Emit cursor shape + position IPC events", "voxy", "1.1"};
}

APICALL EXPORT void PLUGIN_EXIT() {
    if (s_hookShape) {
        s_hookShape->unhook();
        HyprlandAPI::removeFunctionHook(s_handle, s_hookShape);
        s_hookShape = nullptr;
    }
    if (s_hookMove) {
        s_hookMove->unhook();
        HyprlandAPI::removeFunctionHook(s_handle, s_hookMove);
        s_hookMove = nullptr;
    }
}
