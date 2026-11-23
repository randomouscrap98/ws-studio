#ifndef HAL_H
#define HAL_H

#include <stdint.h>
#include <gbdk/metasprites.h>

/* WonderSwan Color hardware abstraction used by the GBVM engine port.
 * Background and sprite paths are implemented. */

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

/* Fill screen 1 with the WSC blank tile (tile 255, BG palette 0) and clear
 * that tile's pixels. The engine calls this on scene load so areas outside a
 * scene smaller than the screen show BG palette 0 colour 0. */
void hal_clear_bkg(void);

/* Sprite tiles are plain GB 2bpp, converted without an index shift. Index 0
 * stays transparent. */
void hal_load_sprite_tiles(uint16_t first, uint16_t count,
                           const uint8_t __far *data, uint8_t bpp);

/* Load count CGB RGB555 palettes into sprite palettes starting at first.
 * GB sprite palette p becomes WSC palette 8+p; all four entries are written. */
void hal_set_sprite_palette(uint8_t first, uint8_t count,
                            const uint16_t __far *cgb_colors);

/* Metasprite drawing. The offset chain is cumulative, as in GBDK: each
 * entry's dx/dy is relative to the previous entry.
 *
 * Coordinates are logical screen pixels, with (0, 0) at the top left. GB OAM
 * hardware coordinates carry a fixed (-8, -16) bias; the HAL removes it so
 * callers can pass logical positions directly.
 *
 * props is OR'd with each entry's props. Palette bits 0-2 select the GB sprite
 * palette, bit 3 adds 256 to the tile index, bits 5/6 flip the tile. The GB
 * behind-BG priority bit (7) is ignored because screen 1 has no equivalent
 * priority bit on WSC.
 *
 * mode is HAL_SPRITE_MODE_8X8 or HAL_SPRITE_MODE_8X16. In 8x16 mode the low
 * tile bit is ignored, the top half is tile & 0xFE, the bottom tile | 1, and
 * a V-flip swaps the halves. flip is HAL_FLIP_NONE/H/V/HV and mirrors both the
 * tile graphics and the cumulative offsets.
 *
 * Returns the number of 8x8 WSC sprite entries added. */
#define HAL_SPRITE_MODE_8X8  0
#define HAL_SPRITE_MODE_8X16 1
#define HAL_FLIP_NONE 0
#define HAL_FLIP_H    1
#define HAL_FLIP_V    2
#define HAL_FLIP_HV   3

void hal_sprites_begin(void);
uint16_t hal_draw_metasprite(const metasprite_t __far *ms, uint16_t base_tile,
                             uint8_t props, int16_t x, int16_t y,
                             uint8_t mode, uint8_t flip);
/* Add offset to the tile field of sprite entries [first, first+count). The
 * engine keeps sprite tiles in the 256..511 half of WSC tile memory. */
void hal_sprite_offset_tiles(uint16_t first, uint16_t count, uint16_t offset);
void hal_sprites_end(void);
uint16_t hal_sprite_count(void);

#endif
