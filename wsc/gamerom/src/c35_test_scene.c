/* C35 orientation-switch test: the town scene with an init script that
 * switches horizontal -> vertical -> horizontal while the scene is live.
 * The exported Sample Town data is reused; only the init script differs. */

#include "gbs_types.h"
#include "d2c_scripts.h"

#include "data/scene_sample_town_bg.h"
#include "data/scene_sample_town_collisions.h"
#include "data/palette_8.h"
#include "data/palette_10.h"
#include "data/sprite_player.h"
#include "data/scene_sample_town_actors.h"
#include "data/scene_sample_town_triggers.h"
#include "data/scene_sample_town_sprites.h"

/* 1 = horizontal (initial), 2 = vertical, 3 = horizontal again. */
volatile UBYTE c35_phase;

const __far struct scene_t scene_c35_switch = {
    .width = 56,
    .height = 56,
    .type = SCENE_TYPE_TOPDOWN,
    .background = TO_FAR_PTR_T(scene_sample_town_bg),
    .collisions = TO_FAR_PTR_T(scene_sample_town_collisions),
    .parallax_rows = {
        PARALLAX_STEP(0, 0, 0)
    },
    .scroll_bounds = {
        .left = 0,
        .top = 0,
        .right = 448,
        .bottom = 448
    },
    .palette = TO_FAR_PTR_T(palette_8),
    .sprite_palette = TO_FAR_PTR_T(palette_10),
    .reserve_tiles = 0,
    .player_sprite = TO_FAR_PTR_T(sprite_player),
    .n_actors = 9,
    .n_triggers = 14,
    .n_sprites = 8,
    .n_projectiles = 0,
    .actors = TO_FAR_PTR_T(scene_sample_town_actors),
    .triggers = TO_FAR_PTR_T(scene_sample_town_triggers),
    .sprites = TO_FAR_PTR_T(scene_sample_town_sprites),
    .script_init = S2C_FPTR_script_c35_switch
};

/* Control for the switch test: identical tick sequence without a switch. */
const __far struct scene_t scene_c35_idle = {
    .width = 56,
    .height = 56,
    .type = SCENE_TYPE_TOPDOWN,
    .background = TO_FAR_PTR_T(scene_sample_town_bg),
    .collisions = TO_FAR_PTR_T(scene_sample_town_collisions),
    .parallax_rows = {
        PARALLAX_STEP(0, 0, 0)
    },
    .scroll_bounds = {
        .left = 0,
        .top = 0,
        .right = 448,
        .bottom = 448
    },
    .palette = TO_FAR_PTR_T(palette_8),
    .sprite_palette = TO_FAR_PTR_T(palette_10),
    .reserve_tiles = 0,
    .player_sprite = TO_FAR_PTR_T(sprite_player),
    .n_actors = 9,
    .n_triggers = 14,
    .n_sprites = 8,
    .n_projectiles = 0,
    .actors = TO_FAR_PTR_T(scene_sample_town_actors),
    .triggers = TO_FAR_PTR_T(scene_sample_town_triggers),
    .sprites = TO_FAR_PTR_T(scene_sample_town_sprites),
    .script_init = S2C_FPTR_script_c35_idle
};
