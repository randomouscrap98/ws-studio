#ifndef HAL_WSC_INTERNAL_H
#define HAL_WSC_INTERNAL_H

#include <wonderful.h>
#include <ws.h>

/* Screen 1 and 2 memory, also used by the background map writers. */
extern volatile ws_screen_t hal_screen;
extern volatile ws_screen_t hal_win_screen;

/* Convert count GB 2bpp tiles to 4bpp at first + t, adding index_shift to
 * every pixel index. */
void hal_wsc_convert_tiles_2bpp(uint16_t first, uint16_t count,
                                const uint8_t __far *data, uint8_t index_shift);

/* Screen-2/window variant of the background tile-map writer. */
void hal_put_win_tiles(uint8_t x, uint8_t y, uint8_t w, uint8_t h,
                       const uint8_t __far *map,
                       const uint8_t __far *attrs, uint8_t map_w);

#endif
