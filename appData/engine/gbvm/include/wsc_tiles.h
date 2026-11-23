#ifndef WSC_TILES_H
#define WSC_TILES_H

/* WonderSwan Color 4bpp tile memory layout.
 *
 * Colour mode has 1024 tiles at WS_TILE_4BPP_MEM(0..1023).  A screen cell
 * can address all 1024 (9 index bits plus the bank bit), but a sprite-table
 * entry only has the 9 index bits, so sprites are limited to 0..511
 * (libws: WS_SPRITE_ATTR_TILE_MASK is 0x1FF).
 *
 *   0..255    GB background bank 0 (including the UI frame/text tiles)
 *   256..511  GB sprite tiles
 *   512..767  GB background bank 1 (cgb_tileset, attribute bit 3 cells,
 *             UI text in bank 1, and the overflow of 256+-tile backgrounds)
 *   1023      the blank tile used outside centred small scenes
 */
#define WSC_TILE_BG_BANK0_BASE 0
#define WSC_TILE_SPRITE_BASE 256
#define WSC_TILE_BG_BANK1_BASE 512
#define WSC_TILE_BG_BANK1_SIZE 256
#define WSC_TILE_BLANK 1023

#endif
