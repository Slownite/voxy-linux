// Pure halo-outline pixel builder. No Hyprland deps — depends on cairo only.
// Split out of main.cpp so it can be linked into the unit-test binary.
#pragma once

#include <cstdint>
#include <vector>

inline constexpr int OUTLINE_HALO = 3;       // outline thickness in buffer pixels
inline constexpr int OUTLINE_PAD  = OUTLINE_HALO + 1;

struct OutlinePixels {
    std::vector<uint8_t> data;   // premultiplied ARGB32, row stride = width*4
    int                  width  = 0;
    int                  height = 0;
};

// Build a colored halo-outline from a source cursor image (premultiplied
// ARGB32, BGRA byte order on little-endian).
//   - sdata/sw/sh/sstride: source cursor pixel buffer.
//   - r,g,b in [0,1]: outline tint.
// Output:
//   - width  = sw + 2 * OUTLINE_PAD
//   - height = sh + 2 * OUTLINE_PAD
//   - data is premultiplied ARGB32, tightly packed (stride = width*4).
//   - the silhouette is punched out, leaving the outline ring only.
// Returns empty OutlinePixels on invalid input.
OutlinePixels buildOutlinePixels(const uint8_t* sdata, int sw, int sh, int sstride,
                                 float r, float g, float b);
