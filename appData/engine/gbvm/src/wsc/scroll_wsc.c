/* WonderSwan Color scroll.c back end.
 *
 * The engine compiles the 8-bit map row/column writes to set_bkg_submap().
 * On WSC screen 1 is a 32x32 array of 16-bit cells, and each cell carries the
 * tile index, palette and flips. Attributes come from the background's CGB
 * attribute map, which the engine keeps in image_attr_ptr.
 */

#include <stdint.h>

#include <wonderful.h>
#include <ws.h>

#include "gbdk/platform.h"
#include "scroll.h"
#include "data_manager.h"
#include "hal.h"
#include "hal_wsc_internal.h"
#include "wsc_tiles.h"

void hal_clear_bkg(void) {
    volatile uint8_t *tile =
        (volatile uint8_t *)WS_TILE_4BPP_MEM(WSC_TILE_BLANK);
    uint16_t i;

    /* Pixel index 1 is GB background colour 0 (hal_load_bkg_tiles shifts
     * every GB index up by one), so the blank area shows palette 0 colour 0
     * rather than the HAL's cleared entry 0. */
    for (i = 0; i < 32; i++)
        tile[i] = (i % 4 == 0) ? 0xFF : 0x00;

    for (i = 0; i < WS_SCREEN_WIDTH_TILES * WS_SCREEN_HEIGHT_TILES; i++)
        hal_screen.cell[i] = WS_SCREEN_ATTR_TILE_EX(WSC_TILE_BLANK);
}

void set_bkg_submap(UINT8 x, UINT8 y, UINT8 w, UINT8 h,
                    const unsigned char __far *map, UINT8 map_w) {
    UINT8 row, col;

    for (row = 0; row < h; row++) {
        UINT16 src_y = (UINT16)y + row;
        if (src_y >= image_tile_height)
            continue;

        for (col = 0; col < w; col++) {
            UINT16 src_x = (UINT16)x + col;
            UINT16 src, index, cell;
            UBYTE tile, attr;

            if (src_x >= image_tile_width)
                continue;

            src = src_y * map_w + src_x;
            tile = map[src];
            attr = image_attr_ptr ? image_attr_ptr[src] : 0;

            index = (UINT16)tile;
            if (attr & 0x08)
                index += WSC_TILE_BG_BANK1_BASE;

            cell = WS_SCREEN_ATTR_TILE_EX(index)
                 | WS_SCREEN_ATTR_PALETTE(attr & 0x07)
                 | ((attr & 0x20) ? WS_SCREEN_ATTR_FLIP_H : 0)
                 | ((attr & 0x40) ? WS_SCREEN_ATTR_FLIP_V : 0);

            hal_screen.cell[((src_y & 31) << 5) | (src_x & 31)] = cell;
        }
    }
}
