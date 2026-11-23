#pragma bank 255

#include "vm.h"

#include "projectiles.h"
#include "data_manager.h"
#include "actor.h"

BANKREF(VM_PROJECTILE)

typedef struct projectile_launch_t {
    upoint16_t pos;
    uint16_t angle;
} projectile_launch_t;

void vm_projectile_launch(SCRIPT_CTX * THIS, UBYTE type, INT16 idx) OLDCALL BANKED {
    projectile_launch_t * params = VM_REF_TO_PTR(idx);
    projectile_launch(type, &params->pos, (UBYTE)params->angle);
}

void vm_projectile_load_type(SCRIPT_CTX * THIS, UBYTE dest_type, UBYTE src_type, UBYTE projectile_def_bank, VM_C_DATA(projectile_def_t) projectile_def) OLDCALL BANKED {
    THIS;
    projectile_def_t * current_def = projectile_defs + dest_type;
    far_ptr_t scene_sprites;
#ifdef __ia16__
    ReadBankedFarPtr(&scene_sprites, (const void __far *)&((const scene_t __far *)current_scene.ptr)->sprites, current_scene.bank);
#else
    ReadBankedFarPtr(&scene_sprites, (const unsigned char *)&((scene_t *)current_scene.ptr)->sprites, current_scene.bank);
#endif
    MemcpyBanked(current_def, projectile_def + src_type, sizeof(projectile_def_t), projectile_def_bank);
    UBYTE idx = IndexOfFarPtr(scene_sprites.ptr, scene_sprites.bank, sprites_len, &current_def->sprite);
    current_def->base_tile = (idx < sprites_len) ? scene_sprites_base_tiles[idx] : 0;
}