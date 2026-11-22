/* C05: load GB background data through the WSC HAL and scroll it. */
#include <stdint.h>
#include "hal.h"
#include "bg_data.h"

volatile uint16_t hal_frames;
volatile uint8_t hal_input;
volatile uint8_t scroll_x;

void main(void) {
    uint8_t x = 0;

    hal_display_init();

    hal_load_bkg_tiles(0, BG_TILE_COUNT, bg_tiles, 2);
    hal_load_bkg_tiles(BG_HI_TILE_FIRST, BG_HI_TILE_COUNT, bg_tiles_hi, 2);
    hal_set_bkg_palette(0, BG_PALETTE_COUNT, bg_palettes);
    hal_put_bkg_tiles(0, 0, BG_MAP_WIDTH, BG_MAP_HEIGHT,
                      bg_map, bg_attrs, BG_MAP_WIDTH);

    hal_scroll_to(0, 0);
    hal_display_on();

    while (1) {
        hal_input = hal_input_read();

        if ((hal_input & J_RIGHT) && x < 8) {
            x++;
            hal_scroll_to(x, 0);
        }

        scroll_x = x;
        hal_frames = hal_vblank_count();
        hal_wait_vblank();
    }
}
