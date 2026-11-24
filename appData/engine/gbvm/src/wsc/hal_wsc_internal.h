#ifndef HAL_WSC_INTERNAL_H
#define HAL_WSC_INTERNAL_H

#include <wonderful.h>
#include <ws.h>

/* Attribute byte flags: UI palette, and the GB background bank 1 window
 * (the CGB text buffer uses the same bank bit as its VRAM bank 1). */
#define HAL_WIN_UI_ATTR 0x80
#define HAL_WIN_BANK1   0x08

/* Screen 1 and 2 memory, also used by the background map writers. */
extern volatile ws_screen_t hal_screen;
extern volatile ws_screen_t hal_win_screen;

/* Screen-2 UI shadow map (8-bit tile index plus one attribute byte). */
extern uint8_t hal_win_tiles[WS_SCREEN_WIDTH_TILES * WS_SCREEN_HEIGHT_TILES];
extern uint8_t hal_win_attrs[WS_SCREEN_WIDTH_TILES * WS_SCREEN_HEIGHT_TILES];

/* Convert count GB 2bpp tiles to 4bpp at first + t, adding index_shift to
 * every pixel index. */
void hal_wsc_convert_tiles_2bpp(uint16_t first, uint16_t count,
                                const uint8_t __far *data, uint8_t index_shift);

/* Rotate tile data already in VRAM in place.  direction > 0 rotates the
 * logical tile 90 degrees clockwise into the physical vertical view;
 * direction < 0 undoes it.  Used by the tile loaders and the runtime
 * orientation switch. */
void hal_wsc_rotate_tiles(uint16_t first, uint16_t count, int8_t direction);
void hal_wsc_rotate_tile(uint16_t index, int8_t direction);

/* Screen-2/window variant of the background tile-map writer. */
void hal_put_win_tiles(uint8_t x, uint8_t y, uint8_t w, uint8_t h,
                       const uint8_t __far *map,
                       const uint8_t __far *attrs, uint8_t map_w);

/* The UI keeps screen 2 as an 8-bit tile-index shadow map (with one attribute
 * byte per cell) and flushes it to the hardware cell array. */
void hal_win_map_put(uint8_t x, uint8_t y, uint8_t w, uint8_t h,
                     const uint8_t __far *map,
                     const uint8_t __far *attrs, uint8_t map_w);

#endif
