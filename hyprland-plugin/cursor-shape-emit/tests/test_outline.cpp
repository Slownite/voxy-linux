// Unit tests for buildOutlinePixels. No Hyprland deps.
//
// Run via `make test` from the parent directory.

#include "../outline.hpp"

#include <cairo/cairo.h>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>

static int g_failed = 0;
static int g_passed = 0;

#define CHECK(cond) do {                                                                 \
    if (cond) {                                                                          \
        ++g_passed;                                                                      \
    } else {                                                                             \
        ++g_failed;                                                                      \
        std::fprintf(stderr, "FAIL %s:%d  %s\n", __FILE__, __LINE__, #cond);             \
    }                                                                                    \
} while (0)

#define CHECK_EQ(a, b) do {                                                              \
    auto _va = (a); auto _vb = (b);                                                      \
    if (_va == _vb) {                                                                    \
        ++g_passed;                                                                      \
    } else {                                                                             \
        ++g_failed;                                                                      \
        std::fprintf(stderr, "FAIL %s:%d  %s == %s : got %lld vs %lld\n",                \
                     __FILE__, __LINE__, #a, #b,                                         \
                     (long long)_va, (long long)_vb);                                    \
    }                                                                                    \
} while (0)

#define TEST(name) static void name(); static const struct name##_reg {                  \
    name##_reg() { tests().push_back({#name, name}); }                                   \
} name##_REG; static void name()

struct TestCase { const char* name; void (*fn)(); };
static std::vector<TestCase>& tests() { static std::vector<TestCase> v; return v; }

// ---------------------------------------------------------------------------
// Pixel helpers: input format is premultiplied ARGB32, BGRA byte order
// on little-endian. Helpers below construct/inspect that layout.
// ---------------------------------------------------------------------------

static void setPx(std::vector<uint8_t>& buf, int w, int x, int y,
                  uint8_t r, uint8_t g, uint8_t b, uint8_t a) {
    uint8_t* p = &buf[(y * w + x) * 4];
    // Premultiply.
    p[0] = (uint8_t)((uint32_t)b * a / 255);
    p[1] = (uint8_t)((uint32_t)g * a / 255);
    p[2] = (uint8_t)((uint32_t)r * a / 255);
    p[3] = a;
}

struct Px { uint8_t b, g, r, a; };
static Px getPx(const OutlinePixels& out, int x, int y) {
    const uint8_t* p = &out.data[(y * out.width + x) * 4];
    return {p[0], p[1], p[2], p[3]};
}

// ---------------------------------------------------------------------------

TEST(empty_input_returns_empty) {
    OutlinePixels out = buildOutlinePixels(nullptr, 0, 0, 0, 1.f, 0.f, 0.f);
    CHECK(out.data.empty());
    CHECK_EQ(out.width, 0);
    CHECK_EQ(out.height, 0);
}

TEST(negative_size_returns_empty) {
    uint8_t pixel[4] = {0xff, 0xff, 0xff, 0xff};
    OutlinePixels out = buildOutlinePixels(pixel, -1, 1, 4, 0.f, 1.f, 0.f);
    CHECK(out.data.empty());
}

TEST(stride_too_small_returns_empty) {
    uint8_t pixel[4] = {0xff, 0xff, 0xff, 0xff};
    OutlinePixels out = buildOutlinePixels(pixel, 1, 1, 2 /* < 1*4 */, 0.f, 1.f, 0.f);
    CHECK(out.data.empty());
}

TEST(zero_alpha_yields_empty_outline) {
    std::vector<uint8_t> in(4 * 4 * 4, 0);
    OutlinePixels out = buildOutlinePixels(in.data(), 4, 4, 16, 0.f, 1.f, 0.f);
    CHECK_EQ(out.width,  4 + 2 * OUTLINE_PAD);
    CHECK_EQ(out.height, 4 + 2 * OUTLINE_PAD);
    bool anyAlpha = false;
    for (uint8_t v : out.data) if (v != 0) { anyAlpha = true; break; }
    CHECK(!anyAlpha);
}

TEST(output_dims_padded_correctly) {
    std::vector<uint8_t> in(8 * 6 * 4, 0);
    OutlinePixels out = buildOutlinePixels(in.data(), 8, 6, 32, 1.f, 0.f, 0.f);
    CHECK_EQ(out.width,  8 + 2 * OUTLINE_PAD);
    CHECK_EQ(out.height, 6 + 2 * OUTLINE_PAD);
    CHECK_EQ((int)out.data.size(), out.width * out.height * 4);
}

TEST(single_opaque_pixel_makes_ring) {
    // Single opaque pixel at (2,2) of a 5x5 source.
    const int sw = 5, sh = 5;
    std::vector<uint8_t> in(sw * sh * 4, 0);
    setPx(in, sw, 2, 2, 255, 255, 255, 255);
    OutlinePixels out = buildOutlinePixels(in.data(), sw, sh, sw * 4, 0.f, 1.f, 0.f);

    // Silhouette pixel position in destination coords.
    const int cx = 2 + OUTLINE_PAD;
    const int cy = 2 + OUTLINE_PAD;

    // Center punched out by DEST_OUT.
    CHECK_EQ((int)getPx(out, cx, cy).a, 0);

    // Halo ring populated: every pixel within Chebyshev distance OUTLINE_HALO
    // (excluding the centre) should have non-zero alpha after dilation.
    for (int oy = -OUTLINE_HALO; oy <= OUTLINE_HALO; ++oy) {
        for (int ox = -OUTLINE_HALO; ox <= OUTLINE_HALO; ++ox) {
            if (ox == 0 && oy == 0) continue;
            CHECK(getPx(out, cx + ox, cy + oy).a > 0);
        }
    }

    // Far outside halo box -> still transparent.
    CHECK_EQ((int)getPx(out, cx + OUTLINE_HALO + 1, cy).a, 0);
    CHECK_EQ((int)getPx(out, cx, cy + OUTLINE_HALO + 1).a, 0);
}

TEST(opaque_pixel_outline_is_green) {
    const int sw = 3, sh = 3;
    std::vector<uint8_t> in(sw * sh * 4, 0);
    setPx(in, sw, 1, 1, 255, 255, 255, 255);
    OutlinePixels out = buildOutlinePixels(in.data(), sw, sh, sw * 4, 0.f, 1.f, 0.f);

    // Sample a fully-painted halo pixel (offset 1 from center, opaque src
    // pixel propagated to it). Premultiplied: g==a, r==b==0 (modulo blending).
    Px p = getPx(out, (1 + OUTLINE_PAD) + 1, 1 + OUTLINE_PAD);
    CHECK(p.a > 200);   // close to opaque after splat
    CHECK_EQ((int)p.r, 0);
    CHECK_EQ((int)p.b, 0);
    CHECK(p.g > 200);   // green channel filled
}

TEST(opaque_pixel_outline_is_orange) {
    const int sw = 3, sh = 3;
    std::vector<uint8_t> in(sw * sh * 4, 0);
    setPx(in, sw, 1, 1, 255, 255, 255, 255);
    OutlinePixels out = buildOutlinePixels(in.data(), sw, sh, sw * 4, 1.0f, 0.67f, 0.0f);

    Px p = getPx(out, (1 + OUTLINE_PAD) + 1, 1 + OUTLINE_PAD);
    CHECK(p.a > 200);
    CHECK(p.r > 200);              // red full
    CHECK(p.g > 100 && p.g < 200); // green mid
    CHECK_EQ((int)p.b, 0);         // no blue
}

TEST(opaque_pixel_premultiplied_invariant) {
    // For an opaque source pixel, premultiplied RGB == RGB * alpha / 255.
    // Tint = (r=1, g=0.5, b=0); on a fully-painted halo pixel we expect
    // (R, G, B, A) ~ (255, 127, 0, 255) — within ±2 rounding tolerance.
    const int sw = 3, sh = 3;
    std::vector<uint8_t> in(sw * sh * 4, 0);
    setPx(in, sw, 1, 1, 255, 255, 255, 255);
    OutlinePixels out = buildOutlinePixels(in.data(), sw, sh, sw * 4, 1.0f, 0.5f, 0.0f);
    Px p = getPx(out, (1 + OUTLINE_PAD) + 1, 1 + OUTLINE_PAD);

    auto near = [](int a, int b) { return (a >= b - 2) && (a <= b + 2); };
    CHECK(near((int)p.a, 255));
    CHECK(near((int)p.r, 255));
    CHECK(near((int)p.g, 127));  // 0.5 * 255
    CHECK(near((int)p.b, 0));
    // Premultiplied invariant: channel <= alpha for all channels.
    CHECK(p.r <= p.a);
    CHECK(p.g <= p.a);
    CHECK(p.b <= p.a);
}

TEST(mid_alpha_input_preserved_in_output) {
    // A source pixel with alpha 128 (50%) — the painted halo pixels should
    // have output alpha proportional to the input alpha (cairo OVER of 50%
    // source over transparent destination = 50% alpha output).
    const int sw = 3, sh = 3;
    std::vector<uint8_t> in(sw * sh * 4, 0);
    setPx(in, sw, 1, 1, 255, 255, 255, 128);  // 50% transparent white
    OutlinePixels out = buildOutlinePixels(in.data(), sw, sh, sw * 4, 0.f, 1.f, 0.f);

    // Sample directly adjacent (offset 1) halo pixel. Output alpha must be
    // between mid input alpha and "fully accumulated" (multiple overlapping
    // 50% paints compound via OVER, raising alpha towards 1).
    Px p = getPx(out, (1 + OUTLINE_PAD) + 1, 1 + OUTLINE_PAD);
    CHECK(p.a >= 128);            // at least one paint at 50% — output >= 50%
    CHECK(p.a < 255);             // can't exceed source-derived ceiling
    // Premultiplied invariant still holds.
    CHECK(p.r <= p.a);
    CHECK(p.g <= p.a);
    CHECK(p.b <= p.a);
    // Centre still punched by DEST_OUT — masked by 50% original.
    Px centre = getPx(out, 1 + OUTLINE_PAD, 1 + OUTLINE_PAD);
    CHECK(centre.a < p.a);        // centre attenuated by punch
}

TEST(symmetric_input_yields_symmetric_outline) {
    // A symmetric source must yield an outline symmetric across both axes.
    const int sw = 7, sh = 7;
    std::vector<uint8_t> in(sw * sh * 4, 0);
    setPx(in, sw, 3, 3, 255, 255, 255, 255);
    OutlinePixels out = buildOutlinePixels(in.data(), sw, sh, sw * 4, 0.f, 1.f, 0.f);

    const int cx = 3 + OUTLINE_PAD;
    const int cy = 3 + OUTLINE_PAD;
    for (int d = 1; d <= OUTLINE_HALO; ++d) {
        CHECK_EQ((int)getPx(out, cx - d, cy).a, (int)getPx(out, cx + d, cy).a);
        CHECK_EQ((int)getPx(out, cx, cy - d).a, (int)getPx(out, cx, cy + d).a);
        CHECK_EQ((int)getPx(out, cx - d, cy - d).a, (int)getPx(out, cx + d, cy + d).a);
    }
}

TEST(row_stride_with_extra_bytes_handled) {
    // Source rows have trailing padding (stride > sw*4). Builder must respect
    // stride and NOT leak the sentinel bytes from the padding region into the
    // output.
    const int sw = 4, sh = 4;
    const int extra = 5;             // extra bytes per row
    const int stride = sw * 4 + extra;
    std::vector<uint8_t> in(stride * sh, 0);
    // Fill row 1 with opaque pixels using the padded stride.
    for (int x = 0; x < sw; ++x) {
        uint8_t* p = &in[1 * stride + x * 4];
        p[0] = p[1] = p[2] = p[3] = 255;
    }
    // Sentinel bytes in padding region — must NOT influence output.
    for (int y = 0; y < sh; ++y)
        for (int b = sw * 4; b < stride; ++b)
            in[y * stride + b] = 0xff;

    OutlinePixels out = buildOutlinePixels(in.data(), sw, sh, stride, 0.f, 1.f, 0.f);
    CHECK_EQ(out.width,  sw + 2 * OUTLINE_PAD);

    // Row OUTLINE_PAD + 1 (centre of row 1's silhouette in dst coords) — punched.
    CHECK_EQ((int)getPx(out, OUTLINE_PAD + 0, OUTLINE_PAD + 1).a, 0);

    // Pixels in the rightmost column of the output (dst x = sw + 2*PAD - 1)
    // can only get paint from src x = sw - 1 + HALO (= sw + HALO - 1 in dst).
    // Beyond that column, output must be all-zero. If stride bytes leaked,
    // we would see paint here.
    const int firstAllZeroCol = sw + OUTLINE_PAD + OUTLINE_HALO;  // exclusive lower bound
    for (int y = 0; y < out.height; ++y) {
        for (int x = firstAllZeroCol; x < out.width; ++x) {
            CHECK_EQ((int)getPx(out, x, y).a, 0);
        }
    }
}

TEST(silhouette_rect_interior_is_punched_out) {
    // 3x3 opaque rect in a 5x5 source. The 3x3 interior of the silhouette in
    // dst-coords must be fully transparent (DEST_OUT), while the ring around
    // it is filled.
    const int sw = 5, sh = 5;
    std::vector<uint8_t> in(sw * sh * 4, 0);
    for (int y = 1; y <= 3; ++y)
        for (int x = 1; x <= 3; ++x)
            setPx(in, sw, x, y, 255, 255, 255, 255);
    OutlinePixels out = buildOutlinePixels(in.data(), sw, sh, sw * 4, 0.f, 1.f, 0.f);

    for (int y = 1; y <= 3; ++y)
        for (int x = 1; x <= 3; ++x)
            CHECK_EQ((int)getPx(out, x + OUTLINE_PAD, y + OUTLINE_PAD).a, 0);

    // Ring pixel adjacent to top of rect — strongly painted.
    CHECK(getPx(out, 2 + OUTLINE_PAD, 0 + OUTLINE_PAD).a > 200);
}

// ---------------------------------------------------------------------------
// Golden fixture: arrow-like silhouette. Output is written to tests/golden/
// on first run; subsequent runs compare against the checked-in file.
// ---------------------------------------------------------------------------

static std::vector<uint8_t> makeArrowSilhouette(int& w, int& h) {
    // 16x16 arrow pointing top-left, similar shape to xcursor "default".
    const int sz = 16;
    w = sz; h = sz;
    std::vector<uint8_t> px(sz * sz * 4, 0);
    for (int y = 0; y < sz; ++y) {
        for (int x = 0; x < sz; ++x) {
            // Triangle: x >= y -> outside; otherwise inside.
            bool inside = (x <= y) && (y < 14) && (x < y + 6);
            if (inside)
                setPx(px, sz, x, y, 255, 255, 255, 255);
        }
    }
    return px;
}

static bool fileExists(const std::string& path) {
    FILE* f = std::fopen(path.c_str(), "rb"); if (!f) return false;
    std::fclose(f); return true;
}

static void savePNG(const OutlinePixels& out, const std::string& path) {
    cairo_surface_t* surf = cairo_image_surface_create_for_data(
        const_cast<uint8_t*>(out.data.data()), CAIRO_FORMAT_ARGB32,
        out.width, out.height, out.width * 4);
    cairo_surface_write_to_png(surf, path.c_str());
    cairo_surface_destroy(surf);
}

static bool loadPNG(const std::string& path, std::vector<uint8_t>& bytes,
                    int& w, int& h) {
    cairo_surface_t* surf = cairo_image_surface_create_from_png(path.c_str());
    if (cairo_surface_status(surf) != CAIRO_STATUS_SUCCESS) {
        cairo_surface_destroy(surf); return false;
    }
    cairo_surface_flush(surf);
    w = cairo_image_surface_get_width(surf);
    h = cairo_image_surface_get_height(surf);
    const int stride = cairo_image_surface_get_stride(surf);
    const uint8_t* data = cairo_image_surface_get_data(surf);
    bytes.resize((size_t)w * h * 4);
    for (int y = 0; y < h; ++y)
        std::memcpy(&bytes[y * w * 4], data + y * stride, w * 4);
    cairo_surface_destroy(surf);
    return true;
}

// Resolve a path relative to the test source file, so the test works
// regardless of the caller's working directory.
static std::string goldenPath(const char* leaf) {
    std::string here = __FILE__;
    auto slash = here.find_last_of('/');
    std::string base = (slash == std::string::npos) ? "." : here.substr(0, slash);
    return base + "/golden/" + leaf;
}

TEST(golden_arrow_outline_matches_fixture) {
    int w, h;
    std::vector<uint8_t> arrow = makeArrowSilhouette(w, h);
    OutlinePixels out = buildOutlinePixels(arrow.data(), w, h, w * 4, 0.13f, 0.80f, 0.33f);

    const std::string path = goldenPath("arrow_green.png");
    if (!fileExists(path)) {
        savePNG(out, path);
        std::fprintf(stderr, "NOTE  golden fixture created: %s — re-run tests\n", path.c_str());
        ++g_passed;
        return;
    }
    std::vector<uint8_t> golden;
    int gw = 0, gh = 0;
    CHECK(loadPNG(path, golden, gw, gh));
    CHECK_EQ(gw, out.width);
    CHECK_EQ(gh, out.height);
    if (gw != out.width || gh != out.height)
        return;

    // Tight per-pixel tolerance: cairo on the same machine is byte-exact in
    // practice. Allow at most 2 LSBs per channel for blending variance across
    // cairo versions, and at most 1% of pixels to diverge at all.
    const int PER_CHANNEL_MAX_DIFF = 2;
    size_t divergentPixels = 0;
    size_t worstChannelDiff = 0;
    const int totalPixels = out.width * out.height;
    for (int p = 0; p < totalPixels; ++p) {
        bool diverged = false;
        for (int c = 0; c < 4; ++c) {
            int d = (int)golden[p * 4 + c] - (int)out.data[p * 4 + c];
            d = d < 0 ? -d : d;
            if ((size_t)d > worstChannelDiff)
                worstChannelDiff = (size_t)d;
            if (d > PER_CHANNEL_MAX_DIFF)
                diverged = true;
        }
        if (diverged) ++divergentPixels;
    }
    const size_t divergentLimit = (size_t)totalPixels / 100;
    CHECK(worstChannelDiff <= (size_t)PER_CHANNEL_MAX_DIFF * 8);  // hard ceiling
    CHECK(divergentPixels <= divergentLimit);
    if (divergentPixels > divergentLimit)
        std::fprintf(stderr,
            "golden divergent pixels: %zu (limit %zu), worst channel diff %zu\n",
            divergentPixels, divergentLimit, worstChannelDiff);
}

// ---------------------------------------------------------------------------

int main(int argc, char** argv) {
    bool regen = (argc > 1 && std::string(argv[1]) == "--regen-golden");
    if (regen) {
        std::fprintf(stderr, "regenerating golden fixtures...\n");
        std::remove(goldenPath("arrow_green.png").c_str());
    }
    for (auto& t : tests()) {
        std::fprintf(stderr, "  %s\n", t.name);
        t.fn();
    }
    std::fprintf(stderr, "\n%d passed, %d failed\n", g_passed, g_failed);
    return g_failed == 0 ? 0 : 1;
}
