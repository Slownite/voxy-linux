// cursor-shape-emit: Hyprland plugin emitting cursor shape events and
// drawing voxy's recording-state outline directly inside the compositor.
//
// Why draw the outline here instead of in a Wayland client?
//   Hyprland renders the cursor on a hardware cursor plane that updates at
//   kernel input rate. A separate wl_surface fed by IPC events will always
//   trail the cursor by ≥1 compositor frame plus the IPC hop. By drawing in
//   the renderer we share the cursor's compositor frame and skip the IPC +
//   GTK frame clock entirely.
//
// Surface:
//   - cursorshape>>name           IPC event when the cursor name changes.
//   - hyprctl dispatch cursorshapequery     re-emit current shape.
//   - hyprctl dispatch voxy:overlay_show         outline ON, recording color.
//   - hyprctl dispatch voxy:overlay_processing   outline ON, processing color.
//   - hyprctl dispatch voxy:overlay_hide         outline OFF.

#include <hyprland/src/plugins/PluginAPI.hpp>
#include <hyprland/src/managers/EventManager.hpp>
#include <hyprland/src/managers/input/InputManager.hpp>
#include <hyprland/src/render/Renderer.hpp>
#include <hyprland/src/render/OpenGL.hpp>
#include <hyprland/src/Compositor.hpp>
#include <hyprland/src/helpers/math/Math.hpp>
#include <string>
#include <format>

static std::string s_lastCursorName;

static CFunctionHook* s_hookShape = nullptr;
static CFunctionHook* s_hookMove  = nullptr;
static HANDLE         s_handle    = nullptr;
static SP<HOOK_CALLBACK_FN> s_renderCb;

// Overlay state — toggled via dispatchers, read in the render hook.
static bool      s_overlayVisible = false;
static int       s_overlayState   = 0;   // 0 = recording, 1 = processing
static Vector2D  s_lastDrawnPos   = {0, 0};

static const double OUTLINE_SIZE   = 40.0;
static const double OUTLINE_STROKE = 2.0;
static const double DAMAGE_PAD     = OUTLINE_SIZE / 2.0 + 4.0;

using FSetCursorFromName = void (*)(void*, const std::string&);
using FOnMouseMoved      = void (*)(void*, IPointer::SMotionEvent);

static void emitShape(const std::string& name) {
    if (g_pEventManager)
        g_pEventManager->postEvent({.event = "cursorshape", .data = name});
}

static void damageAroundCursor() {
    if (!s_overlayVisible || !g_pInputManager || !g_pHyprRenderer)
        return;
    const Vector2D pos = g_pInputManager->getMouseCoordsInternal();
    const int pad = (int)DAMAGE_PAD;
    const int sz  = pad * 2;
    g_pHyprRenderer->damageBox((int)(pos.x - pad),
                               (int)(pos.y - pad), sz, sz);
    if (s_lastDrawnPos.x != 0 || s_lastDrawnPos.y != 0) {
        g_pHyprRenderer->damageBox((int)(s_lastDrawnPos.x - pad),
                                   (int)(s_lastDrawnPos.y - pad), sz, sz);
    }
}

static void damageAllMonitors() {
    if (!g_pHyprRenderer || !g_pCompositor)
        return;
    for (auto& m : g_pCompositor->m_vMonitors) {
        if (m)
            g_pHyprRenderer->damageMonitor(m);
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
    // While the overlay is up we need framebuffer damage on every motion so
    // the renderer keeps producing frames and our render hook runs. The HW
    // cursor plane updates without scheduling framebuffer work.
    if (s_overlayVisible)
        damageAroundCursor();
}

static void onRender(void*, SCallbackInfo&, std::any data) {
    if (!s_overlayVisible)
        return;
    eRenderStage stage;
    try {
        stage = std::any_cast<eRenderStage>(data);
    } catch (const std::bad_any_cast&) {
        return;
    }
    if (stage != RENDER_LAST_MOMENT)
        return;
    if (!g_pHyprOpenGL || !g_pInputManager)
        return;

    auto monitor = g_pHyprOpenGL->m_RenderData.pMonitor;
    if (!monitor)
        return;

    const Vector2D pos = g_pInputManager->getMouseCoordsInternal();
    const double lx = pos.x - monitor->vecPosition.x;
    const double ly = pos.y - monitor->vecPosition.y;
    if (lx < 0 || ly < 0 || lx >= monitor->vecSize.x || ly >= monitor->vecSize.y)
        return;

    const CHyprColor color = (s_overlayState == 0)
        ? CHyprColor(0.13f, 0.80f, 0.33f, 1.0f)
        : CHyprColor(1.0f,  0.67f, 0.0f, 1.0f);

    const double half = OUTLINE_SIZE / 2.0;
    const double sw   = OUTLINE_STROKE;

    CBox top    {lx - half,        ly - half,        OUTLINE_SIZE, sw};
    CBox bottom {lx - half,        ly + half - sw,   OUTLINE_SIZE, sw};
    CBox left   {lx - half,        ly - half,        sw,           OUTLINE_SIZE};
    CBox right  {lx + half - sw,   ly - half,        sw,           OUTLINE_SIZE};

    g_pHyprOpenGL->renderRect(&top,    color);
    g_pHyprOpenGL->renderRect(&bottom, color);
    g_pHyprOpenGL->renderRect(&left,   color);
    g_pHyprOpenGL->renderRect(&right,  color);

    s_lastDrawnPos = pos;
}

static SDispatchResult onCursorShapeQuery(std::string args) {
    if (!s_lastCursorName.empty())
        emitShape(s_lastCursorName);
    return {.success = true};
}

static SDispatchResult onOverlayShow(std::string args) {
    s_overlayState   = 0;
    s_overlayVisible = true;
    damageAllMonitors();
    return {.success = true};
}

static SDispatchResult onOverlayProcessing(std::string args) {
    s_overlayState = 1;
    damageAllMonitors();
    return {.success = true};
}

static SDispatchResult onOverlayHide(std::string args) {
    // Damage first so the next frame clears the strip, then mark hidden.
    damageAllMonitors();
    s_overlayVisible = false;
    s_lastDrawnPos   = {0, 0};
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

    s_renderCb = HyprlandAPI::registerCallbackDynamic(handle, "render", onRender);

    HyprlandAPI::addDispatcherV2(handle, "cursorshapequery",      onCursorShapeQuery);
    HyprlandAPI::addDispatcherV2(handle, "voxy:overlay_show",       onOverlayShow);
    HyprlandAPI::addDispatcherV2(handle, "voxy:overlay_processing", onOverlayProcessing);
    HyprlandAPI::addDispatcherV2(handle, "voxy:overlay_hide",       onOverlayHide);

    return {"cursor-shape-emit", "Cursor shape IPC + voxy in-compositor overlay", "voxy", "2.0"};
}

APICALL EXPORT void PLUGIN_EXIT() {
    s_overlayVisible = false;
    s_renderCb.reset();
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
