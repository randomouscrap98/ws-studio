/* WonderSwan Color HAL: GB background data conversion. */
#include <stdint.h>
#include <wonderful.h>
#include <ws.h>
#include "hal.h"
#include "hal_wsc_internal.h"
#include "wsc_tiles.h"

/* Reverse the bit order of one byte. */
static uint8_t hal_reverse_bits(uint8_t value) {
    value = (uint8_t)(((value & 0xF0u) >> 4) | ((value & 0x0Fu) << 4));
    value = (uint8_t)(((value & 0xCCu) >> 2) | ((value & 0x33u) << 2));
    value = (uint8_t)(((value & 0xAAu) >> 1) | ((value & 0x55u) << 1));
    return value;
}

/* In-place transpose of an 8x8 bit matrix stored as eight bytes.  The three
 * butterfly stages swap 1x1, 2x2 and 4x4 blocks. */
static void hal_transpose8(uint8_t *a) {
    uint8_t j, k, t, m = 0xFFu;

    for (j = 4; j; j >>= 1) {
        m ^= (uint8_t)(m << j);
        for (k = 0; k < 8; k = (uint8_t)((k + j + 1) & ~j)) {
            t = (uint8_t)(((a[k] >> j) ^ a[k + j]) & m);
            a[k] ^= (uint8_t)(t << j);
            a[k + j] ^= t;
        }
    }
}

/* Rotate one 4bpp tile in place.  direction > 0 maps logical pixel (x, y) to
 * physical (7 - y, x), which is the clockwise rotation used by vertical
 * mode; direction < 0 is its inverse.  The four plane rows are transposed
 * with bit operations instead of visiting all 64 pixels individually. */
void hal_wsc_rotate_tile(uint16_t index, int8_t direction) {
    volatile uint8_t *mem = (volatile uint8_t *)WS_TILE_4BPP_MEM(index);
    uint8_t plane, row;
    uint8_t a[8];

    for (plane = 0; plane < 4; plane++) {
        for (row = 0; row < 8; row++)
            a[row] = mem[row * 4 + plane];

        hal_transpose8(a);

        if (direction > 0) {
            /* Rotate clockwise: the transposed rows come back reversed. */
            for (row = 0; row < 8; row++)
                mem[row * 4 + plane] = a[7 - row];
        } else {
            /* Counter-clockwise: transpose, then mirror every row. */
            for (row = 0; row < 8; row++)
                mem[row * 4 + plane] = hal_reverse_bits(a[row]);
        }
    }
}

void hal_wsc_rotate_tiles(uint16_t first, uint16_t count, int8_t direction) {
    uint16_t i;

    for (i = 0; i < count; i++)
        hal_wsc_rotate_tile((uint16_t)(first + i), direction);
}

void hal_wsc_convert_tiles_2bpp(uint16_t first, uint16_t count,
                                const uint8_t __far *data, uint8_t index_shift) {
    uint16_t t, row, bit;

    for (t = 0; t < count; t++) {
        volatile uint8_t *dst =
            (volatile uint8_t *)WS_TILE_4BPP_MEM(first + t);
        const uint8_t __far *src = data + t * 16;

        for (row = 0; row < 8; row++) {
            uint8_t lo = src[row * 2];
            uint8_t hi = src[row * 2 + 1];
            uint8_t p0 = 0, p1 = 0, p2 = 0, p3 = 0;

            for (bit = 0; bit < 8; bit++) {
                uint8_t mask = (uint8_t)(0x80 >> bit);
                uint8_t index = (uint8_t)(
                    ((lo & mask) ? 1 : 0) |
                    ((hi & mask) ? 2 : 0)) + index_shift;

                if (index & 1) p0 |= mask;
                if (index & 2) p1 |= mask;
                if (index & 4) p2 |= mask;
                if (index & 8) p3 |= mask;
            }

            /* WSC 4bpp planar: four plane bytes per row, bit 7 leftmost. */
            dst[row * 4 + 0] = p0;
            dst[row * 4 + 1] = p1;
            dst[row * 4 + 2] = p2;
            dst[row * 4 + 3] = p3;
        }

        if (hal_orientation() == HAL_ORIENTATION_VERTICAL)
            hal_wsc_rotate_tile((uint16_t)(first + t), 1);
    }
}

void hal_load_bkg_tiles(uint16_t first, uint16_t count,
                        const uint8_t __far *data, uint8_t bpp) {
    if (bpp != 2)
        return;

    /* GB background colour 0 stays opaque: shift every index up by one. */
    hal_wsc_convert_tiles_2bpp(first, count, data, 1);
}

void hal_load_bkg_tiles_ram(uint16_t first, uint16_t count,
                            const uint8_t *data) {
    uint16_t t, row, bit;

    for (t = 0; t < count; t++) {
        volatile uint8_t *dst =
            (volatile uint8_t *)WS_TILE_4BPP_MEM(first + t);
        const uint8_t *src = data + t * 16;

        for (row = 0; row < 8; row++) {
            uint8_t lo = src[row * 2];
            uint8_t hi = src[row * 2 + 1];
            uint8_t p0 = 0, p1 = 0, p2 = 0, p3 = 0;

            for (bit = 0; bit < 8; bit++) {
                uint8_t mask = (uint8_t)(0x80 >> bit);
                uint8_t index = (uint8_t)(
                    ((lo & mask) ? 1 : 0) |
                    ((hi & mask) ? 2 : 0)) + 1;

                if (index & 1) p0 |= mask;
                if (index & 2) p1 |= mask;
                if (index & 4) p2 |= mask;
                if (index & 8) p3 |= mask;
            }

            dst[row * 4 + 0] = p0;
            dst[row * 4 + 1] = p1;
            dst[row * 4 + 2] = p2;
            dst[row * 4 + 3] = p3;
        }

        if (hal_orientation() == HAL_ORIENTATION_VERTICAL)
            hal_wsc_rotate_tile((uint16_t)(first + t), 1);
    }
}

void hal_set_bkg_palette(uint8_t first, uint8_t count,
                         const uint16_t __far *cgb_colors) {
    uint8_t p, i;

    for (p = 0; p < count; p++) {
        volatile uint16_t *dst = WS_SCREEN_COLOR_MEM(first + p);

        dst[0] = 0;
        for (i = 0; i < 4; i++) {
            uint16_t c = cgb_colors[p * 4 + i];
            uint8_t r = (uint8_t)((c & 0x1F) >> 1);
            uint8_t g = (uint8_t)(((c >> 5) & 0x1F) >> 1);
            uint8_t b = (uint8_t)(((c >> 10) & 0x1F) >> 1);

            dst[i + 1] = WS_RGB(r, g, b);
        }
    }
}

static void hal_put_screen_tiles(volatile ws_screen_t *screen,
                                 uint8_t x, uint8_t y, uint8_t w, uint8_t h,
                                 const uint8_t __far *map,
                                 const uint8_t __far *attrs, uint8_t map_w) {
    uint8_t row, col;
    uint8_t vertical = (hal_orientation() == HAL_ORIENTATION_VERTICAL);

    for (row = 0; row < h; row++) {
        for (col = 0; col < w; col++) {
            uint8_t map_x = (uint8_t)(x + col);
            uint8_t map_y = (uint8_t)(y + row);
            uint16_t off = (uint16_t)map_y * map_w + map_x;
            uint8_t tile = map[off];
            uint8_t attr = attrs ? attrs[off] : 0;
            uint16_t index = (uint16_t)tile;
            uint16_t cell;
            uint16_t flip_h;
            uint16_t flip_v;
            uint16_t dst;

            if (attr & 0x08)
                index += WSC_TILE_BG_BANK1_BASE;

            flip_h = (attr & 0x20) ? WS_SCREEN_ATTR_FLIP_H : 0;
            flip_v = (attr & 0x40) ? WS_SCREEN_ATTR_FLIP_V : 0;
            if (vertical) {
                uint16_t tmp = flip_h;
                flip_h = flip_v;
                flip_v = tmp;
            }

            cell = WS_SCREEN_ATTR_TILE_EX(index)
                 | WS_SCREEN_ATTR_PALETTE(attr & 0x07)
                 | flip_h | flip_v;

            if (vertical)
                dst = ((uint16_t)map_x & 31) * 32 +
                      ((27 - (uint16_t)map_y) & 31);
            else
                dst = ((uint16_t)(map_y & 31) << 5) | (map_x & 31);
            screen->cell[dst] = cell;
        }
    }
}

void hal_put_bkg_tiles(uint8_t x, uint8_t y, uint8_t w, uint8_t h,
                       const uint8_t __far *map,
                       const uint8_t __far *attrs, uint8_t map_w) {
    hal_put_screen_tiles(&hal_screen, x, y, w, h, map, attrs, map_w);
}

void hal_put_win_tiles(uint8_t x, uint8_t y, uint8_t w, uint8_t h,
                       const uint8_t __far *map,
                       const uint8_t __far *attrs, uint8_t map_w) {
    hal_win_map_put(x, y, w, h, map, attrs, map_w);
}
