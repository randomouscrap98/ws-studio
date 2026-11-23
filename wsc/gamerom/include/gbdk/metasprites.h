#ifndef GAMEROM_GBDK_METASPRITES_H
#define GAMEROM_GBDK_METASPRITES_H

/* Minimal GBDK metasprite definitions for the WSC engine boot ROM. */

#include <stdint.h>

#define metasprite_end -128

typedef struct metasprite_t {
    int8_t dy, dx;
    uint8_t dtile;
    uint8_t props;
} metasprite_t;

#define METASPR_TERM {metasprite_end, 0, 0, 0}
#define METASPR_ITEM(dy, dx, dtile, props) {(dy), (dx), (dtile), (props)}

#endif
