#ifndef WS_SURVEY_GBDK_METASPRITES_H
#define WS_SURVEY_GBDK_METASPRITES_H

#include <gbdk/platform.h>

#define metasprite_end -128

typedef struct metasprite_t {
    INT8 dy, dx;
    UINT8 dtile;
    UINT8 props;
} metasprite_t;

typedef struct OAM_item_t {
    UINT8 y, x;
    UINT8 tile;
    UINT8 prop;
} OAM_item_t;

#define METASPR_TERM {metasprite_end, 0, 0, 0}
#define METASPR_ITEM(dy, dx, dtile, props) {dy, dx, dtile, props}

extern volatile OAM_item_t shadow_OAM[40];

UINT8 move_metasprite(const metasprite_t *metasprite, UINT8 base_tile, UINT8 base_sprite, UINT8 x, UINT8 y);
UINT8 move_metasprite_flipx(const metasprite_t *metasprite, UINT8 base_tile, UINT8 base_sprite, UINT8 x, UINT8 y);
UINT8 move_metasprite_flipy(const metasprite_t *metasprite, UINT8 base_tile, UINT8 base_sprite, UINT8 x, UINT8 y);
UINT8 move_metasprite_flipxy(const metasprite_t *metasprite, UINT8 base_tile, UINT8 base_sprite, UINT8 x, UINT8 y);

#endif
