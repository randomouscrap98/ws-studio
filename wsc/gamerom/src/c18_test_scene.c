/* C18 tile-map tests.
 *
 * scene_c18_big reuses the generated 16x18 background with 264 bank-0 tiles,
 * a cgb_tileset and attribute-bit-3 cells.  scene_c18_blank uses the exported
 * logo background (20x18, centred on the 224-px screen) and a long dialogue
 * that reaches text tile 0xFF, so the blank border can be checked.
 */

#include "gbs_types.h"
#include "d2c_scripts.h"

#include "c18_bg_data.h"
#include "data/bg_logo.h"
#include "data/scene_logo_collisions.h"
#include "data/palette_0.h"
#include "data/palette_10.h"
#include "data/sprite_player.h"

const __far struct scene_t scene_c18_big = {
    .width = 16,
    .height = 18,
    .type = SCENE_TYPE_TOPDOWN,
    .background = TO_FAR_PTR_T(c18_bg),
    .collisions = TO_FAR_PTR_T(c18_collisions),
    .parallax_rows = {
        PARALLAX_STEP(0, 0, 0)
    },
    .palette = TO_FAR_PTR_T(c18_bg_palette),
    .sprite_palette = TO_FAR_PTR_T(palette_10),
    .reserve_tiles = 0,
    .player_sprite = TO_FAR_PTR_T(sprite_player),
    .n_actors = 0,
    .n_triggers = 0,
    .n_sprites = 0,
    .n_projectiles = 0,
    .script_init = S2C_FPTR_script_c18_stop
};

const __far struct scene_t scene_c18_blank = {
    .width = 20,
    .height = 18,
    .type = SCENE_TYPE_TOPDOWN,
    .background = TO_FAR_PTR_T(bg_logo),
    .collisions = TO_FAR_PTR_T(scene_logo_collisions),
    .parallax_rows = {
        PARALLAX_STEP(0, 0, 0)
    },
    .palette = TO_FAR_PTR_T(palette_0),
    .sprite_palette = TO_FAR_PTR_T(palette_10),
    .reserve_tiles = 0,
    .player_sprite = TO_FAR_PTR_T(sprite_player),
    .n_actors = 0,
    .n_triggers = 0,
    .n_sprites = 0,
    .n_projectiles = 0,
    .script_init = S2C_FPTR_script_c18_blank
};
