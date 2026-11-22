#ifndef HAL_H
#define HAL_H

#include <stdint.h>

/* WonderSwan Color hardware abstraction used by the GBVM engine port.
 * Only the background path needed by the C05 tests is implemented. */

/* GB joypad bits; X1/X2/X3/X4 map to up/right/down/left. */
#ifndef J_RIGHT
#define J_RIGHT 0x01
#endif
#ifndef J_LEFT
#define J_LEFT 0x02
#endif
#ifndef J_UP
#define J_UP 0x04
#endif
#ifndef J_DOWN
#define J_DOWN 0x08
#endif
#ifndef J_A
#define J_A 0x10
#endif
#ifndef J_B
#define J_B 0x20
#endif
#ifndef J_SELECT
#define J_SELECT 0x40
#endif
#ifndef J_START
#define J_START 0x80
#endif

/* Visible size. The values are variables so a later mode can switch the
 * screen orientation at runtime. */
extern uint8_t hal_screen_w;      /* tiles */
extern uint8_t hal_screen_h;      /* tiles */
extern uint16_t hal_screen_w_px;  /* pixels */
extern uint16_t hal_screen_h_px;  /* pixels */

/* Display and frame timing. hal_display_init also installs and enables the
 * vblank interrupt used by hal_wait_vblank/hal_vblank_count. */
void hal_display_init(void);
void hal_display_on(void);
void hal_display_off(void);
void hal_wait_vblank(void);
uint16_t hal_vblank_count(void);

/* Returns a GB J_* mask. Select is not mapped yet. */
uint8_t hal_input_read(void);

/* Load count GB 2bpp tiles at logical tile index first, converting each
 * pixel index i to i+1 so GB background colour 0 stays opaque. */
void hal_load_bkg_tiles(uint16_t first, uint16_t count,
                        const uint8_t __far *data, uint8_t bpp);

/* Load count CGB RGB555 palettes into WSC palettes starting at first.
 * Each palette is four colours written to entries 1-4; entry 0 is cleared. */
void hal_set_bkg_palette(uint8_t first, uint8_t count,
                         const uint16_t __far *cgb_colors);

/* Write a w*h rectangle from a 32x32-map/attribute pair (stride map_w) into
 * the WSC screen, converting each pair to one 16-bit screen cell. */
void hal_put_bkg_tiles(uint8_t x, uint8_t y, uint8_t w, uint8_t h,
                       const uint8_t __far *map,
                       const uint8_t __far *attrs, uint8_t map_w);

/* Scroll the background to the given logical pixel position. */
void hal_scroll_to(int16_t x, int16_t y);

#endif
