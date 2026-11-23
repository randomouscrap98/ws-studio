/* C05/C06: load GB background and sprite data through the WSC HAL. */
#include <stdint.h>
#include "hal.h"
#include "bg_data.h"
#include "spr_data.h"

volatile uint16_t hal_frames;
volatile uint8_t hal_input;
volatile uint8_t scroll_x;
volatile int16_t player_x;
volatile int16_t player_y;
volatile uint16_t sprite_count;
volatile uint8_t hal_ready;

static void draw_sprites(void) {
    hal_sprites_begin();
    hal_draw_metasprite(spr_player_metasprite, SPR_PLAYER_BASE, 0,
                        player_x, player_y,
                        HAL_SPRITE_MODE_8X16, HAL_FLIP_NONE);
    hal_draw_metasprite(spr_accent_metasprite, SPR_ACCENT_BASE, 0,
                        ACCENT_X, ACCENT_Y,
                        HAL_SPRITE_MODE_8X8, HAL_FLIP_HV);
    sprite_count = hal_sprite_count();
    hal_sprites_end();
}

void main(void) {
    uint8_t x = 0;

    hal_display_init();

    hal_load_bkg_tiles(0, BG_TILE_COUNT, bg_tiles, 2);
    hal_load_bkg_tiles(BG_HI_TILE_FIRST, BG_HI_TILE_COUNT, bg_tiles_hi, 2);
    hal_set_bkg_palette(0, BG_PALETTE_COUNT, bg_palettes);
    hal_put_bkg_tiles(0, 0, BG_MAP_WIDTH, BG_MAP_HEIGHT,
                      bg_map, bg_attrs, BG_MAP_WIDTH);

    hal_load_sprite_tiles(SPR_TILE_FIRST, SPR_TILE_COUNT, spr_tiles, 2);
    hal_set_sprite_palette(0, SPR_PALETTE_COUNT, spr_palettes);

    hal_scroll_to(0, 0);
    player_x = PLAYER_START_X;
    player_y = PLAYER_START_Y;
    draw_sprites();

    hal_display_on();

    hal_ready = 1;
    while (1) {
        hal_input = hal_input_read();

        if (hal_input & J_RIGHT) {
            player_x++;
            if (x < 8) {
                x++;
                hal_scroll_to(x, 0);
            }
        }
        if (hal_input & J_LEFT)
            player_x--;
        if (hal_input & J_UP)
            player_y--;
        if (hal_input & J_DOWN)
            player_y++;

        scroll_x = x;
        draw_sprites();
        hal_frames = hal_vblank_count();
        hal_wait_vblank();
    }
}
