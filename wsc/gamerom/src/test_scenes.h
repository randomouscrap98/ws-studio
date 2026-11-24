#ifndef GAMEROM_TEST_SCENES_H
#define GAMEROM_TEST_SCENES_H

#include "gbs_types.h"

/* Boot ids used by wsrun's --boot-id. Keep in step with tests/run.py. */
enum {
    BOOT_SCENE_LOGO = 0,
    BOOT_SCENE_TOWN,
    BOOT_SCENE_TOWN_WALK,
    BOOT_SCENE_C13,
    BOOT_SCENE_C14,
    BOOT_SCENE_C15_INSTANT,
    BOOT_SCENE_C15_SPEED,
    BOOT_SCENE_C15_VAR,
    BOOT_SCENE_C16_CHOICE,
    BOOT_SCENE_C17_EDGE,
    BOOT_SCENE_C18_BIG,
    BOOT_SCENE_C18_BLANK,
    BOOT_SCENE_PLATFORM_DEEPER,
    BOOT_SCENE_PLATFORM_PATH,
    BOOT_SCENE_PLATFORM_PARALLAX,
    BOOT_SCENE_COUNT
};

extern const __far struct scene_t scene_c13_test;
extern const __far struct scene_t scene_c14_test;
extern const __far struct scene_t scene_c15_instant;
extern const __far struct scene_t scene_c15_speed;
extern const __far struct scene_t scene_c15_var;
extern const __far struct scene_t scene_c16_choice;
extern const __far struct scene_t scene_c17_edge;
extern const __far struct scene_t scene_c18_big;
extern const __far struct scene_t scene_c18_blank;

#endif
