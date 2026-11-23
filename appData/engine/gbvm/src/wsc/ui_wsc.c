/* WonderSwan Color UI backend: screen-2 shadow map and frame drawing.
 *
 * The shared UI code addresses the GB window as a byte map (one tile index
 * per cell, 32-cell rows).  Screen 2 stores 16-bit cells, so the UI writes
 * this shadow map and hal_window_flush() converts it to hardware cells. */
#include <stdint.h>

#include <wonderful.h>
#include <ws.h>

#include "gbdk/platform.h"
#include "ui.h"
#include "scroll.h"
#include "hal.h"
#include "hal_wsc_internal.h"

#define WSC_WIN_CELLS (WS_SCREEN_WIDTH_TILES * WS_SCREEN_HEIGHT_TILES)

UBYTE vwf_tile_data[16 * 2];

/* ui_a.s _ui_time_masks */
const UBYTE ui_time_masks[] = {
    0x00, 0x00, 0x01, 0x03, 0x07, 0x0F, 0x1F, 0x3F
};

static uint16_t win_offset(const UBYTE *addr) {
    return (uint16_t)(addr - hal_win_tiles);
}

static void win_mark_ui(UBYTE *addr, UBYTE width) {
    uint16_t offset = win_offset(addr);
    UBYTE i;

    for (i = 0; i < width && offset + i < WSC_WIN_CELLS; i++)
        hal_win_attrs[offset + i] = HAL_WIN_UI_ATTR;
}

UINT8 *GetWinAddr(void) {
    return hal_win_tiles;
}

/* Text rendering on the background layer is not ported yet; the code that
 * uses this returns through the excluded text opcodes. */
UINT8 *GetBkgAddr(void) {
    return (UINT8 *)(void *)hal_screen.cell;
}

void scroll_rect(UBYTE *base_addr, UBYTE w, UBYTE h, UBYTE fill) {
    UBYTE row, col;
    uint16_t offset = win_offset(base_addr);

    if (h == 0)
        return;

    for (row = 0; row + 1 < h; row++) {
        for (col = 0; col < w; col++) {
            uint16_t dst = offset + (uint16_t)row * 32 + col;
            uint16_t src = dst + 32;

            if (dst >= WSC_WIN_CELLS || src >= WSC_WIN_CELLS)
                continue;
            hal_win_tiles[dst] = hal_win_tiles[src];
            hal_win_attrs[dst] = hal_win_attrs[src];
        }
    }
    for (col = 0; col < w; col++) {
        uint16_t dst = offset + (uint16_t)(h - 1) * 32 + col;

        if (dst >= WSC_WIN_CELLS)
            continue;
        hal_win_tiles[dst] = fill;
        hal_win_attrs[dst] = HAL_WIN_UI_ATTR;
    }
}

void fill_win_rect(UINT8 x, UINT8 y, UINT8 w, UINT8 h, UINT8 tile) {
    UBYTE row, col;

    for (row = 0; row < h; row++) {
        for (col = 0; col < w; col++) {
            uint16_t offset = (((uint16_t)y + row) & 31) * 32 +
                              (((uint16_t)x + col) & 31);

            hal_win_tiles[offset] = tile;
            hal_win_attrs[offset] = HAL_WIN_UI_ATTR;
        }
    }
}

void set_win_tile_xy(UINT8 x, UINT8 y, UINT8 tile) {
    uint16_t offset = ((uint16_t)y & 31) * 32 + ((uint16_t)x & 31);

    hal_win_tiles[offset] = tile;
    hal_win_attrs[offset] = HAL_WIN_UI_ATTR;
}

void set_xy_win_submap(const UBYTE __far *source, UBYTE bank, UBYTE width,
                       UBYTE x, UBYTE y, UBYTE w, UBYTE h) {
    UBYTE row, col;
    (void)bank;

    for (row = 0; row < h; row++) {
        for (col = 0; col < w; col++) {
            uint16_t dst = (((uint16_t)y + row) & 31) * 32 +
                           (((uint16_t)x + col) & 31);

            hal_win_tiles[dst] = source[(uint16_t)row * width + col];
            hal_win_attrs[dst] = 0;
        }
    }
}

void set_vram_byte(void *dest, UINT8 value) {
    uint16_t offset = win_offset((const UBYTE *)dest);

    if (offset >= WSC_WIN_CELLS)
        return;
    hal_win_tiles[offset] = value;
    hal_win_attrs[offset] = HAL_WIN_UI_ATTR;
}

/* ui_a.s _ui_draw_frame_row, rewritten in C. */
void ui_draw_frame_row(void *dest, UBYTE tile, UBYTE width) {
    UBYTE *d = (UBYTE *)dest;
    UBYTE i;

    if (width == 0)
        return;
    d[0] = tile;
    if (width == 1)
        return;
    for (i = 1; i + 1 < width; i++)
        d[i] = (UBYTE)(tile + 1);
    d[width - 1] = (UBYTE)(tile + 2);
    win_mark_ui(d, width);
}

/* ui_a.s ui_load_tiles() loads the white/black text tiles from RAM with
 * set_bkg_data().  This is the near-data 2bpp loader for those two tiles. */
void set_bkg_data(UINT8 first, UINT8 count, const void *data) {
    const uint8_t *src = (const uint8_t *)data;
    uint16_t t, row, bit;

    for (t = 0; t < count; t++) {
        volatile uint8_t *dst =
            (volatile uint8_t *)WS_TILE_4BPP_MEM(first + t);

        for (row = 0; row < 8; row++) {
            uint8_t lo = src[t * 16 + row * 2];
            uint8_t hi = src[t * 16 + row * 2 + 1];
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
    }
}
