// cursor-shape-emit: Hyprland plugin emitting cursor shape events and
// drawing voxy's recording-state outline directly inside the compositor.
//
// Why draw the outline here instead of in a Wayland client?
//   Hyprland renders the cursor on a hardware cursor plane that updates at
//   kernel input rate. A separate wl_surface fed by IPC events will always
//   trail the cursor by >=1 compositor frame plus the IPC hop. Drawing in
//   the renderer shares the cursor's compositor frame and skips the IPC +
//   client frame clock entirely.
//
// Surface:
//   - cursorshape>>name           IPC event when the cursor name changes.
//   - hyprctl dispatch cursorshapequery     re-emit current shape.
//   - hyprctl dispatch voxy:overlay_show         outline ON, recording color.
//   - hyprctl dispatch voxy:overlay_processing   outline ON, processing color.
//   - hyprctl dispatch voxy:overlay_hide         outline OFF.
//
// Rendering contract:
//   We queue a CTexPassElement to g_pHyprRenderer->m_renderPass during the
//   RENDER_LAST_MOMENT signal. Hyprland's renderer flushes m_renderPass.render()
//   inside endRender(), which runs immediately after the LAST_MOMENT emit
//   (see upstream src/render/Renderer.cpp). If that ordering ever changes,
//   the outline will stop appearing — re-check that contract on Hyprland bumps.

#include "outline.hpp"

#include <hyprland/src/plugins/PluginAPI.hpp>
#include <hyprland/src/managers/EventManager.hpp>
#include <hyprland/src/managers/CursorManager.hpp>
#include <hyprland/src/managers/PointerManager.hpp>
#include <hyprland/src/managers/input/InputManager.hpp>
#include <hyprland/src/render/Renderer.hpp>
#include <hyprland/src/render/OpenGL.hpp>
#include <hyprland/src/render/Texture.hpp>
#include <hyprland/src/render/pass/TexPassElement.hpp>
#include <hyprland/src/Compositor.hpp>
#include <hyprland/src/event/EventBus.hpp>
#include <hyprland/src/helpers/math/Math.hpp>
#include <hyprutils/signal/Signal.hpp>
#include <drm_fourcc.h>
#include <optional>
#include <string>
#include <vector>
#include <array>

static std::string s_lastCursorName;

static CFunctionHook* s_hookShape = nullptr;
static CFunctionHook* s_hookMove  = nullptr;
static HANDLE         s_handle    = nullptr;
static Hyprutils::Signal::CHyprSignalListener s_renderCb;

static bool                    s_overlayVisible = false;
static int                     s_overlayState   = 0;   // 0 = recording, 1 = processing
static std::optional<Vector2D> s_lastDrawnPos;

static const double DAMAGE_PAD = 96.0;  // logical pixels, covers any cursor size + halo

using FSetCursorFromName = void (*)(void*, const std::string&);
using FOnMouseMoved      = void (*)(void*, IPointer::SMotionEvent);

struct OutlineTex {
    SP<CTexture> tex;
    int          texW  = 0;       // texture width in buffer pixels (incl. pad)
    int          texH  = 0;       // texture height in buffer pixels (incl. pad)
    int          pad   = 0;       // halo padding included in texture
    Vector2D     hotspotLogical;  // hotspot from cursor image (logical coords)
    Vector2D     bufSize;         // cursor buffer pixel size
    float        bufScale = 1.f;  // buffer scale factor
};

// Cache indexed by current cursor buffer pointer. Invalidated on theme/shape swap.
static std::array<OutlineTex, 2> s_currentOutlines;
static void*                     s_cachedBufferPtr = nullptr;
// Sticky last-good outline kept per-state for use when the current cursor
// buffer is unreadable (e.g. client-set wl_surface cursor on a brief grab).
static std::array<OutlineTex, 2> s_lastGoodOutlines;
static Hyprutils::Signal::CHyprSignalListener s_cursorChangedCb;

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
    if (s_lastDrawnPos) {
        g_pHyprRenderer->damageBox((int)(s_lastDrawnPos->x - pad),
                                   (int)(s_lastDrawnPos->y - pad), sz, sz);
    }
}

static void damageAllMonitors() {
    if (!g_pHyprRenderer || !g_pCompositor)
        return;
    for (auto& m : g_pCompositor->m_monitors) {
        if (m)
            g_pHyprRenderer->damageMonitor(m);
    }
}

// Wrap pixel data from buildOutlinePixels into a CTexture (uploads to GL
// synchronously inside CTexture's ctor via glTexImage2D, so the source
// vector can be freed immediately after).
static SP<CTexture> uploadOutlineTexture(const OutlinePixels& px) {
    if (px.data.empty() || px.width <= 0 || px.height <= 0)
        return nullptr;
    return makeShared<CTexture>(DRM_FORMAT_ARGB8888,
                                const_cast<uint8_t*>(px.data.data()),
                                (uint32_t)(px.width * 4),
                                Vector2D{(double)px.width, (double)px.height},
                                false);
}

static const OutlineTex* getOrBuildOutline(int state) {
    if (!g_pPointerManager)
        return nullptr;
    const auto& img = g_pPointerManager->currentCursorImage();
    if (!img.pBuffer)
        return nullptr;
    void* bufId = img.pBuffer.get();

    if (bufId != s_cachedBufferPtr) {
        s_currentOutlines[0] = {};
        s_currentOutlines[1] = {};
        s_cachedBufferPtr = bufId;
    }
    if (s_currentOutlines[state].tex)
        return &s_currentOutlines[state];

    if (!img.pBuffer->isSynchronous())
        return nullptr;
    // Copy fields out of img before begin/endDataPtr to avoid holding the
    // const-ref across calls that might rebind m_currentCursorImage.
    const Vector2D hotspot  = img.hotspot;
    const Vector2D bufSize  = img.pBuffer->size;
    const float    bufScale = img.scale;

    auto [data, fmt, stride] = img.pBuffer->beginDataPtr(0);
    if (!data || fmt != DRM_FORMAT_ARGB8888) {
        img.pBuffer->endDataPtr();
        return nullptr;
    }
    const int sw = (int)bufSize.x;
    const int sh = (int)bufSize.y;

    const float r = (state == 0) ? 0.13f : 1.00f;
    const float g = (state == 0) ? 0.80f : 0.67f;
    const float b = (state == 0) ? 0.33f : 0.00f;

    OutlinePixels px = buildOutlinePixels(data, sw, sh, (int)stride, r, g, b);
    img.pBuffer->endDataPtr();

    SP<CTexture> tex = uploadOutlineTexture(px);
    if (!tex)
        return nullptr;

    OutlineTex built;
    built.tex            = tex;
    built.texW           = px.width;
    built.texH           = px.height;
    built.pad            = OUTLINE_PAD;
    built.hotspotLogical = hotspot;
    built.bufSize        = bufSize;
    built.bufScale       = bufScale;

    s_currentOutlines[state]  = built;
    s_lastGoodOutlines[state] = std::move(built);
    return &s_currentOutlines[state];
}

void hkSetCursorFromName(void* self, const std::string& name) {
    if (name != s_lastCursorName) {
        s_lastCursorName = name;
        emitShape(name);
    }
    if (s_hookShape && s_hookShape->m_original)
        (*(FSetCursorFromName)s_hookShape->m_original)(self, name);
}

void hkOnMouseMoved(void* self, IPointer::SMotionEvent ev) {
    if (s_hookMove && s_hookMove->m_original)
        (*(FOnMouseMoved)s_hookMove->m_original)(self, ev);
    if (s_overlayVisible)
        damageAroundCursor();
}

static void onRender(eRenderStage stage) {
    if (!s_overlayVisible)
        return;
    if (stage != RENDER_LAST_MOMENT)
        return;
    if (!g_pHyprOpenGL || !g_pInputManager)
        return;

    auto monitor = g_pHyprOpenGL->m_renderData.pMonitor;
    if (!monitor)
        return;
    // Mirror compositor cursor visibility — respect hide_on_key_press etc.
    static bool s_prevVisible = true;
    const bool curVisible = !g_pHyprRenderer || g_pHyprRenderer->shouldRenderCursor();
    if (s_prevVisible && !curVisible) {
        // Cursor just hidden — damage so the previous outline clears next frame.
        damageAroundCursor();
    }
    s_prevVisible = curVisible;
    if (!curVisible)
        return;

    const Vector2D pos = g_pInputManager->getMouseCoordsInternal();
    const double scale = monitor->m_scale;
    const double lx = (pos.x - monitor->m_position.x) * scale;
    const double ly = (pos.y - monitor->m_position.y) * scale;
    if (lx < 0 || ly < 0 || lx >= monitor->m_pixelSize.x || ly >= monitor->m_pixelSize.y)
        return;

    const OutlineTex* ot = getOrBuildOutline(s_overlayState);
    if (!ot || !ot->tex) {
        // Buffer unreadable this frame (e.g. brief client wl_surface cursor).
        // Reuse last good outline so the user still sees something.
        if (s_lastGoodOutlines[s_overlayState].tex)
            ot = &s_lastGoodOutlines[s_overlayState];
    }
    if (!ot || !ot->tex)
        return;

    const double ratio  = scale / (double)ot->bufScale;
    const double hotXpx = ot->hotspotLogical.x * scale;
    const double hotYpx = ot->hotspotLogical.y * scale;
    const double padPx  = ot->pad * ratio;
    const double boxW   = ot->texW * ratio;
    const double boxH   = ot->texH * ratio;
    const double boxX   = lx - hotXpx - padPx;
    const double boxY   = ly - hotYpx - padPx;

    CTexPassElement::SRenderData d;
    d.tex = ot->tex;
    d.box = CBox{boxX, boxY, boxW, boxH};
    d.a   = 1.0f;
    g_pHyprRenderer->m_renderPass.add(makeUnique<CTexPassElement>(d));

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
    damageAllMonitors();
    s_overlayVisible = false;
    s_lastDrawnPos.reset();
    return {.success = true};
}

// Picks the function whose demangled name matches one of the suffix candidates
// (full signature suffix to avoid hooking the wrong overload).
static void* findUniqueOverload(HANDLE handle, const char* name, const char* classQual,
                                std::initializer_list<const char*> sigSuffixes) {
    auto matches = HyprlandAPI::findFunctionsByName(handle, name);
    for (auto& m : matches) {
        if (m.demangled.find(classQual) == std::string::npos)
            continue;
        for (auto* suffix : sigSuffixes) {
            if (m.demangled.find(suffix) != std::string::npos)
                return m.address;
        }
    }
    return nullptr;
}

APICALL EXPORT std::string PLUGIN_API_VERSION() {
    return HYPRLAND_API_VERSION;
}

APICALL EXPORT PLUGIN_DESCRIPTION_INFO PLUGIN_INIT(HANDLE handle) {
    s_handle = handle;

    void* shapeTarget = findUniqueOverload(handle, "setCursorFromName", "CCursorManager",
                                           {"(std::__cxx11::basic_string<char", "(std::string"});
    if (shapeTarget) {
        s_hookShape = HyprlandAPI::createFunctionHook(handle, shapeTarget, (void*)hkSetCursorFromName);
        if (s_hookShape) s_hookShape->hook();
    }
    if (!shapeTarget || !s_hookShape) {
        HyprlandAPI::addNotification(handle,
            "voxy: cursor-shape-emit could not hook setCursorFromName — cursorshape IPC events disabled",
            CHyprColor(1.0f, 0.5f, 0.0f, 1.0f), 5000.0f);
    }

    void* moveTarget = findUniqueOverload(handle, "onMouseMoved", "CInputManager",
                                          {"(IPointer::SMotionEvent)", "SMotionEvent"});
    if (moveTarget) {
        s_hookMove = HyprlandAPI::createFunctionHook(handle, moveTarget, (void*)hkOnMouseMoved);
        if (s_hookMove) s_hookMove->hook();
    }
    if (!moveTarget || !s_hookMove) {
        HyprlandAPI::addNotification(handle,
            "voxy: cursor-shape-emit could not hook onMouseMoved — outline tracking degraded",
            CHyprColor(1.0f, 0.5f, 0.0f, 1.0f), 5000.0f);
    }

    s_renderCb = Event::bus()->m_events.render.stage.listen([](eRenderStage stage) { onRender(stage); });
    // Damage on cursor swap so the outline tracks the new shape immediately,
    // without requiring a mouse move to trigger a redraw.
    if (g_pPointerManager) {
        s_cursorChangedCb = g_pPointerManager->m_events.cursorChanged.listen([]() {
            if (s_overlayVisible)
                damageAroundCursor();
        });
    }

    HyprlandAPI::addDispatcherV2(handle, "cursorshapequery",      onCursorShapeQuery);
    HyprlandAPI::addDispatcherV2(handle, "voxy:overlay_show",       onOverlayShow);
    HyprlandAPI::addDispatcherV2(handle, "voxy:overlay_processing", onOverlayProcessing);
    HyprlandAPI::addDispatcherV2(handle, "voxy:overlay_hide",       onOverlayHide);

    return {"cursor-shape-emit", "Cursor shape IPC + voxy in-compositor outline", "voxy", "2.2"};
}

APICALL EXPORT void PLUGIN_EXIT() {
    s_overlayVisible = false;
    s_renderCb.reset();
    s_cursorChangedCb.reset();
    s_currentOutlines[0] = {};
    s_currentOutlines[1] = {};
    s_lastGoodOutlines[0] = {};
    s_lastGoodOutlines[1] = {};
    s_cachedBufferPtr = nullptr;
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
