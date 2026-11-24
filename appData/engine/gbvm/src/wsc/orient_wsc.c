/* WonderSwan Color runtime screen-orientation switch.
 *
 * The logical screen stays the coordinate system every engine subsystem
 * uses.  This file only changes the HAL's logical size, rotates the tile
 * data already in VRAM, and asks the normal engine paths to repaint. */

#include <stdint.h>

#include "hal.h"
#include "scroll.h"
#include "data_manager.h"
#include "parallax.h"
#include "ui.h"
#include "hal_wsc_internal.h"
#include "wsc_tiles.h"

/* Number of vblank frames the last switch took, including the in-place tile
 * rotation and the repaint.  Tests read this after the switch. */
uint16_t hal_orientation_switch_frames;

void hal_screen_switch_orientation(uint8_t orientation) {
    uint8_t target = (orientation == HAL_ORIENTATION_VERTICAL)
        ? HAL_ORIENTATION_VERTICAL
        : HAL_ORIENTATION_HORIZONTAL;
    uint16_t start;
    uint8_t window_closed;

    if (target == hal_orientation())
        return;

    start = hal_vblank_count();
    /* A window placed below the old screen is the UI's "closed" sentinel;
     * carry that state over to the new height instead of making it visible
     * when the logical screen grows. */
    window_closed = !hal_window_visible();

    if (target == HAL_ORIENTATION_VERTICAL) {
        /* Replace the scene's parallax bands before the repaint: vertical
         * mode has no horizontal split. */
        hal_parallax_vertical_enter();
        hal_screen_set_vertical();
        /* 0..255 background bank 0, 256..511 sprites, 512..767 bank 1.
         * The blank tile has no pattern to rotate. */
        hal_wsc_rotate_tiles(WSC_TILE_BG_BANK0_BASE, 768, 1);
    } else {
        hal_wsc_rotate_tiles(WSC_TILE_BG_BANK0_BASE, 768, -1);
        hal_screen_set_width(224);
        hal_parallax_vertical_leave();
    }

    /* Drop the cells written in the other orientation, then force the scroll
     * code to render the whole logical viewport again. */
    hal_clear_bkg();
    if (window_closed)
        win_pos_y = win_dest_pos_y = (UBYTE)hal_screen_h_px;
    if (hal_window_visible())
        hal_window_set(hal_window_x(), hal_window_y());

    scroll_set_center(image_width, image_height);
    scroll_x = 0x7FFF;
    scroll_y = 0x7FFF;
    scroll_update();
    hal_window_flush();

    hal_orientation_switch_frames = (uint16_t)(hal_vblank_count() - start);
}
