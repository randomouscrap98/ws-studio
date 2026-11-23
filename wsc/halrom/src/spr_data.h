/* Hand-made GB-format sprite data for the C06 HAL sprites test ROM. */
#ifndef HALROM_SPR_DATA_H
#define HALROM_SPR_DATA_H

#include <stdint.h>
#include <gbdk/metasprites.h>

#define SPR_TILE_FIRST 16
#define SPR_TILE_COUNT 6
#define SPR_PLAYER_BASE 16
#define SPR_ACCENT_BASE 20
#define SPR_PALETTE_COUNT 2

#define PLAYER_START_X 16
#define PLAYER_START_Y 24
#define ACCENT_X 112
#define ACCENT_Y 32

extern const uint8_t __far spr_tiles[];
extern const uint16_t __far spr_palettes[];
extern const metasprite_t __far spr_player_metasprite[];
extern const metasprite_t __far spr_accent_metasprite[];

#endif
