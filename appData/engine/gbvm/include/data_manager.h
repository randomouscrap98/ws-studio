#ifndef SCENE_H
#define SCENE_H

#include <gbdk/platform.h>
#include "gbs_types.h"

#ifdef __ia16__
/* Exported scene objects and their arrays live in far ROM. */
#define DATA_PTR(T) const T __far *
#else
#define DATA_PTR(T) const T *
#endif

extern far_ptr_t current_scene;
extern UBYTE image_bank;
extern UBYTE image_attr_bank;
extern UBYTE collision_bank;
#ifdef __ia16__
extern const unsigned char __far *image_ptr;
extern const unsigned char __far *image_attr_ptr;
#else
extern unsigned char *image_ptr;
extern unsigned char *image_attr_ptr;
#endif
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
UBYTE load_scene(DATA_PTR(scene_t) scene, UBYTE bank, UBYTE init_data) BANKED;

UBYTE load_sprite(UBYTE sprite_offset, DATA_PTR(spritesheet_t) sprite, UBYTE bank) BANKED;
void load_player(void) BANKED;
#ifdef __ia16__
void load_emote(const unsigned char __far * tiles, UBYTE bank) BANKED;
void load_animations(DATA_PTR(spritesheet_t) sprite, UBYTE bank, UWORD animation_set, animation_t * res_animations) NONBANKED;
void load_bounds(DATA_PTR(spritesheet_t) sprite, UBYTE bank, rect16_t * res_bounds) BANKED;
#else
void load_emote(const unsigned char * tiles, UBYTE bank) BANKED;
void load_animations(const spritesheet_t *sprite, UBYTE bank, UWORD animation_set, animation_t * res_animations) NONBANKED;
void load_bounds(const spritesheet_t * sprite, UBYTE bank, rect16_t * res_bounds) BANKED;
#endif

#endif
