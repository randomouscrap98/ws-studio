#ifndef SCENE_H
#define SCENE_H

#include <gbdk/platform.h>
#include "gbs_types.h"

extern far_ptr_t current_scene;
extern UBYTE image_bank;
extern UBYTE image_attr_bank;
extern UBYTE collision_bank;
extern const unsigned char FAR *image_ptr;
extern const unsigned char FAR *image_attr_ptr;
extern UBYTE image_tile_width;
extern UBYTE image_tile_height;
extern UINT16 image_width;
extern UINT16 image_height;
extern UINT16 image_width_subpx;
extern UINT16 image_height_subpx;
extern scene_type_e scene_type;
extern UBYTE actors_len;
extern UBYTE sprites_len;
extern UBYTE actors_len;
extern LCD_isr_e scene_LCD_type;

#define SCENE_STACK_SIZE    8
extern scene_stack_item_t scene_stack[SCENE_STACK_SIZE];
extern scene_stack_item_t * scene_stack_ptr;

#define MAX_SCENE_SPRITES   64
extern UBYTE scene_sprites_base_tiles[MAX_SCENE_SPRITES];

void load_init(void) BANKED;
UBYTE load_scene(const scene_t FAR * scene, UBYTE bank, UBYTE init_data) BANKED;

UBYTE load_sprite(UBYTE sprite_offset, const spritesheet_t FAR * sprite, UBYTE bank) BANKED;
void load_player(void) BANKED;
void load_emote(const unsigned char FAR * tiles, UBYTE bank) BANKED;
void load_animations(const spritesheet_t FAR * sprite, UBYTE bank, UWORD animation_set, animation_t * res_animations) NONBANKED;
void load_bounds(const spritesheet_t FAR * sprite, UBYTE bank, rect16_t * res_bounds) BANKED;

#endif
