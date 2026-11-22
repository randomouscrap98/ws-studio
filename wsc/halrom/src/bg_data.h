/* Hand-made GB-format background data for the C05 HAL test ROM.
 *
 * Tiles are GB 2bpp (16 bytes each, low/high plane per row, bit 7 leftmost).
 * Palettes are CGB RGB555 words (0bBBBBBGGGGGRRRRR), four colours each.
 * The map and attribute map are 32x32 bytes.  Attribute bits: 0-2 palette,
 * 3 VRAM bank (+256 tile index), 5 H-flip, 6 V-flip, 7 priority (ignored).
 */
#ifndef HALROM_BG_DATA_H
#define HALROM_BG_DATA_H

#include <stdint.h>

#define BG_TILE_COUNT 8
#define BG_HI_TILE_COUNT 2
#define BG_HI_TILE_FIRST 256
#define BG_PALETTE_COUNT 3
#define BG_MAP_WIDTH 32
#define BG_MAP_HEIGHT 32

extern const uint8_t __far bg_tiles[];
extern const uint8_t __far bg_tiles_hi[];
extern const uint16_t __far bg_palettes[];
extern const uint8_t __far bg_map[];
extern const uint8_t __far bg_attrs[];

#endif
