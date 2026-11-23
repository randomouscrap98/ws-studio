#ifndef HAL_WSC_INTERNAL_H
#define HAL_WSC_INTERNAL_H

#include <wonderful.h>
#include <ws.h>

/* Screen 1 memory, also used by the background map writer. */
extern volatile ws_screen_t hal_screen;

/* Convert count GB 2bpp tiles to 4bpp at first + t, adding index_shift to
 * every pixel index. */
void hal_wsc_convert_tiles_2bpp(uint16_t first, uint16_t count,
                                const uint8_t __far *data, uint8_t index_shift);

#endif
