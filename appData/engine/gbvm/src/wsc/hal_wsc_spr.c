/* WonderSwan Color HAL: sprite tiles, palettes and metasprites. */
#include <stdint.h>
#include <wonderful.h>
#include <ws.h>
#include "hal.h"
#include "hal_wsc_internal.h"

/* The hardware reads the sprite table from a 512-byte aligned IRAM address;
 * .iramx_sprite tells wf-wswantool about both requirements. */
static volatile ws_sprite_table_t hal_sprite_table
    __attribute__((section(".iramx_sprite")));

static uint16_t hal_sprite_entries;

void hal_load_sprite_tiles(uint16_t first, uint16_t count,
                           const uint8_t __far *data, uint8_t bpp) {
    if (bpp != 2)
        return;

    /* Sprite colour 0 is transparent, so the indices are not shifted. */
    hal_wsc_convert_tiles_2bpp(first, count, data, 0);
}

void hal_set_sprite_palette(uint8_t first, uint8_t count,
                            const uint16_t __far *cgb_colors) {
    uint8_t p, i;

    for (p = 0; p < count; p++) {
        volatile uint16_t *dst = WS_SPRITE_COLOR_MEM(first + p);

        for (i = 0; i < 4; i++) {
            uint16_t c = cgb_colors[p * 4 + i];
            uint8_t r = (uint8_t)((c & 0x1F) >> 1);
            uint8_t g = (uint8_t)(((c >> 5) & 0x1F) >> 1);
            uint8_t b = (uint8_t)(((c >> 10) & 0x1F) >> 1);

            dst[i] = WS_RGB(r, g, b);
        }
    }
}

void hal_sprites_begin(void) {
    hal_sprite_entries = 0;
}

static void hal_sprite_add(uint16_t tile, int16_t x, int16_t y,
                           uint16_t attr) {
    volatile ws_sprite_t *sprite;

    /* Cull a whole 8x8 entry that cannot touch the runtime screen.  A partly
     * visible left/top entry is kept: its 8-bit coordinate (e.g. -4 -> 252)
     * is interpreted as signed again by the WSC sprite hardware. */
    if (x >= (int16_t)hal_screen_w_px || x + 8 <= 0 ||
        y >= (int16_t)hal_screen_h_px || y + 8 <= 0)
        return;
    if (hal_sprite_entries >= WS_SPRITE_MAX_COUNT)
        return;

    sprite = &hal_sprite_table.entry[hal_sprite_entries++];
    /* WSC sprites default to behind screen 2.  GB sprites are drawn above the
     * window, so put every entry in front; actor rendering hides covered
     * actors explicitly to reproduce the GB window rule. */
    sprite->attr = (uint16_t)(WS_SPRITE_ATTR_TILE(tile) |
                              WS_SPRITE_ATTR_PRIORITY |
                              (attr & ~WS_SPRITE_ATTR_TILE_MASK));
    sprite->y = (uint8_t)y;
    sprite->x = (uint8_t)x;
}

uint16_t hal_draw_metasprite(const metasprite_t __far *ms, uint16_t base_tile,
                             uint8_t props, int16_t x, int16_t y,
                             uint8_t mode, uint8_t flip) {
    uint16_t first = hal_sprite_entries;
    int16_t cur_x = x, cur_y = y;

    for (;;) {
        uint8_t entry_props;
        uint8_t flip_h, flip_v;
        uint16_t tile, attr;
        int16_t dx, dy;

        if (ms->dy == metasprite_end)
            break;

        entry_props = (uint8_t)(props | ms->props);
        flip_h = (uint8_t)((flip & HAL_FLIP_H) != 0) ^
                 ((entry_props & 0x20) != 0);
        flip_v = (uint8_t)((flip & HAL_FLIP_V) != 0) ^
                 ((entry_props & 0x40) != 0);

        dx = (int16_t)ms->dx;
        dy = (int16_t)ms->dy;
        if (flip & HAL_FLIP_H)
            dx = (int16_t)-dx;
        if (flip & HAL_FLIP_V)
            dy = (int16_t)-dy;
        cur_x = (int16_t)(cur_x + dx);
        cur_y = (int16_t)(cur_y + dy);

        tile = (uint16_t)((base_tile + ms->dtile) & 0xFF);
        if (entry_props & 0x08)
            tile += 256;

        attr = WS_SPRITE_ATTR_PALETTE(entry_props & 0x07);
        if (flip_h)
            attr |= WS_SPRITE_ATTR_FLIP_H;
        if (flip_v)
            attr |= WS_SPRITE_ATTR_FLIP_V;

        if (mode == HAL_SPRITE_MODE_8X16) {
            uint16_t top = (uint16_t)(tile & 0xFFFE);

            if (flip_v) {
                /* The hardware swaps the halves as well as flipping them. */
                hal_sprite_add((uint16_t)(top | 1), cur_x, cur_y, attr);
                hal_sprite_add(top, cur_x, (int16_t)(cur_y + 8), attr);
            } else {
                hal_sprite_add(top, cur_x, cur_y, attr);
                hal_sprite_add((uint16_t)(top | 1), cur_x,
                               (int16_t)(cur_y + 8), attr);
            }
        } else {
            hal_sprite_add(tile, cur_x, cur_y, attr);
        }

        ms++;
    }

    return (uint16_t)(hal_sprite_entries - first);
}

void hal_sprites_end(void) {
    ws_display_set_sprite_address((const void __wf_iram *)&hal_sprite_table);
    outportb(WS_SPR_FIRST_PORT, 0);
    outportb(WS_SPR_COUNT_PORT, (uint8_t)hal_sprite_entries);
}

uint16_t hal_sprite_count(void) {
    return hal_sprite_entries;
}
