/* WonderSwan Color HAL: GB background data conversion. */
#include <stdint.h>
#include <wonderful.h>
#include <ws.h>
#include "hal.h"
#include "hal_wsc_internal.h"

void hal_load_bkg_tiles(uint16_t first, uint16_t count,
                        const uint8_t __far *data, uint8_t bpp) {
    uint16_t t, row, bit;

    if (bpp != 2)
        return;

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
                    ((hi & mask) ? 2 : 0)) + 1;

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

void hal_put_bkg_tiles(uint8_t x, uint8_t y, uint8_t w, uint8_t h,
                       const uint8_t __far *map,
                       const uint8_t __far *attrs, uint8_t map_w) {
    uint8_t row, col;

    for (row = 0; row < h; row++) {
        for (col = 0; col < w; col++) {
            uint8_t map_x = (uint8_t)(x + col);
            uint8_t map_y = (uint8_t)(y + row);
            uint16_t off = (uint16_t)map_y * map_w + map_x;
            uint8_t tile = map[off];
            uint8_t attr = attrs[off];
            uint16_t index = (uint16_t)tile;
            uint16_t cell;

            if (attr & 0x08)
                index += 256;

            cell = WS_SCREEN_ATTR_TILE_EX(index)
                 | WS_SCREEN_ATTR_PALETTE(attr & 0x07)
                 | ((attr & 0x20) ? WS_SCREEN_ATTR_FLIP_H : 0)
                 | ((attr & 0x40) ? WS_SCREEN_ATTR_FLIP_V : 0);

            hal_screen.cell[((uint16_t)(map_y & 31) << 5) |
                            (map_x & 31)] = cell;
        }
    }
}
