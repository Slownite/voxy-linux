// Pure halo-outline pixel builder. No Hyprland deps — cairo only.
//
// Algorithm (matches the original Python `_build_cursor_outline`):
//   1. Build a tinted source: premultiplied ARGB32 where RGB is the target
//      colour, weighted by source alpha. Alpha stays as in the source.
//   2. Paint the tinted source onto a padded destination at every offset in
//      the (2*HALO+1)² box. Cairo's OVER operator antialiases the edges.
//   3. DEST_OUT with the tinted source punches the original silhouette out of
//      the destination, leaving the antialiased outline ring.

#include "outline.hpp"

#include <cairo/cairo.h>

#include <algorithm>
#include <cstdint>

OutlinePixels buildOutlinePixels(const uint8_t* sdata, int sw, int sh, int sstride,
                                 float r, float g, float b) {
    OutlinePixels out;
    if (!sdata || sw <= 0 || sh <= 0 || sstride < sw * 4)
        return out;

    const int pad = OUTLINE_PAD;
    const int dw  = sw + pad * 2;
    const int dh  = sh + pad * 2;

    const uint8_t R = (uint8_t)std::clamp((int)(r * 255.f), 0, 255);
    const uint8_t G = (uint8_t)std::clamp((int)(g * 255.f), 0, 255);
    const uint8_t B = (uint8_t)std::clamp((int)(b * 255.f), 0, 255);

    // Tinted source — premultiplied ARGB32 BGRA byte order on little-endian.
    std::vector<uint8_t> tinted((size_t)sw * sh * 4, 0);
    for (int y = 0; y < sh; ++y) {
        const uint8_t* srow = sdata + (size_t)y * sstride;
        uint8_t*       trow = tinted.data() + (size_t)y * sw * 4;
        for (int x = 0; x < sw; ++x) {
            const uint8_t a = srow[x * 4 + 3];
            trow[x * 4 + 0] = (uint8_t)(((uint32_t)a * B) / 255u);
            trow[x * 4 + 1] = (uint8_t)(((uint32_t)a * G) / 255u);
            trow[x * 4 + 2] = (uint8_t)(((uint32_t)a * R) / 255u);
            trow[x * 4 + 3] = a;
        }
    }

    cairo_surface_t* tintedSurf = cairo_image_surface_create_for_data(
        tinted.data(), CAIRO_FORMAT_ARGB32, sw, sh, sw * 4);
    cairo_surface_t* dst = cairo_image_surface_create(CAIRO_FORMAT_ARGB32, dw, dh);
    cairo_t*         cr  = cairo_create(dst);

    for (int oy = -OUTLINE_HALO; oy <= OUTLINE_HALO; ++oy) {
        for (int ox = -OUTLINE_HALO; ox <= OUTLINE_HALO; ++ox) {
            if (ox == 0 && oy == 0) continue;
            cairo_set_source_surface(cr, tintedSurf, pad + ox, pad + oy);
            cairo_paint(cr);
        }
    }
    cairo_set_operator(cr, CAIRO_OPERATOR_DEST_OUT);
    cairo_set_source_surface(cr, tintedSurf, pad, pad);
    cairo_paint(cr);

    cairo_destroy(cr);
    cairo_surface_flush(dst);

    const uint8_t* dstData   = cairo_image_surface_get_data(dst);
    const int      dstStride = cairo_image_surface_get_stride(dst);

    out.width  = dw;
    out.height = dh;
    out.data.resize((size_t)dw * dh * 4);
    for (int y = 0; y < dh; ++y) {
        const uint8_t* srcRow = dstData + (size_t)y * dstStride;
        uint8_t*       outRow = out.data.data() + (size_t)y * dw * 4;
        std::copy(srcRow, srcRow + dw * 4, outRow);
    }

    cairo_surface_destroy(dst);
    cairo_surface_destroy(tintedSurf);
    return out;
}
