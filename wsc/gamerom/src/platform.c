/* WSC platform hooks for the portable GBVM core on the boot ROM. */

#include <stdbool.h>
#include <stdint.h>

#include <wonderful.h>
#include <ws.h>

#include "vm.h"
#include "hal.h"
#include "d2c_scripts.h"
#include "d2c_manifest.h"
#include "test_scenes.h"

/* wsrun patches these bytes after the magic in the ROM image before boot:
 * byte 7 is the boot id, byte 8 the logical screen width in pixels (0 or
 * 224 keep the default full-width display). */
const volatile __far uint8_t wsc_boot_slot[9] = {
    'W', 'S', 'C', 'B', 'O', 'O', 'T', 0, 224
};

struct boot_entry {
    const struct scene_t __far *scene;
    INT16 x;
    INT16 y;
};

/* Start scene and position for each test id. All scenes share the exported
 * data above, so the table only adds one scene object per test. */
static const struct boot_entry __far boot_table[BOOT_SCENE_COUNT] = {
    { &scene_logo, 0, 0 },
    { &scene_sample_town, 12800, 12800 },        /* 400, 400 px */
    { &scene_sample_town, 3584, 10496 },         /* 112, 328 px */
    { &scene_c13_test, 1536, 2560 },             /* 48, 80 px */
    { &scene_c14_test, 1536, 2560 },
    { &scene_c15_instant, 1536, 2560 },
    { &scene_c15_speed, 1536, 2560 },
    { &scene_c15_var, 1536, 2560 },
    { &scene_c16_choice, 1536, 2560 },
    { &scene_c17_edge, 1536, 2560 },
    { &scene_c18_big, 0, 0 },
    { &scene_c18_blank, 0, 0 },
    { &scene_deeper_underground, 1280, 1024 },  /* 5, 4 tiles */
    { &scene_path_to_sample_town, 1024, 2304 },  /* 4, 9 tiles */
    { &scene_parallax_example, 15360, 3328 },    /* 60, 13 tiles */
    { &scene_path_to_sample_town, 14592, 3328 }, /* 57, 13 tiles */
    { &scene_space_battle, 2048, 2304 },        /* 8, 9 tiles */
    { &scene_player_s_house, 2560, 2560 },      /* 10, 10 tiles */
    { &scene_cave, 3328, 2816 },                /* 13, 11 tiles */
    { &scene_title_screen, 2560, 2560 },        /* 10, 10 tiles */
};

/* Called by the generated bootstrap before the first scene is loaded. */
void wsc_boot_select(far_ptr_t *scene, INT16 *x, INT16 *y) {
    UBYTE id = wsc_boot_slot[7];
    const struct boot_entry __far *entry;

    /* Before the first scene load, so every engine and HAL path sees the
     * selected logical width. */
    hal_screen_set_width(wsc_boot_slot[8]);

    if (id >= BOOT_SCENE_COUNT) id = 0;
    entry = &boot_table[id];
    scene->bank = 0;
    scene->ptr = entry->scene;
    *x = entry->x;
    *y = entry->y;
}

/* One far const array per converted script bank. Slot 0 is unused: script
 * banks start at 1 and bank 0 means "no script", as on the Game Boy. */
static const uint8_t __far *const vm_banks[D2C_BANK_COUNT + 1] = {
    (const uint8_t __far *)0,
    D2C_BANK_LIST
};

const uint8_t __far *vm_bank_base(UBYTE bank) {
    return (bank >= 1 && bank <= D2C_BANK_COUNT)
        ? vm_banks[bank] : (const uint8_t __far *)0;
}

UBYTE *vm_ram_ptr(UWORD idx) {
    return vm_ram_syms[idx];
}

UWORD sys_time;

void wait_vbl_done(void) {
    hal_wait_vblank();
    sys_time++;
}

/* GBDK's rand state.  The engine's save blob stores this exact variable, so a
 * load restores the random sequence too. */
UWORD __rand_seed;

void initrand(UWORD seed) {
    __rand_seed = seed;
}

UWORD randw(void) {
    /* GBDK-2020 4.5.0 libc/asm/sm83/rand.s: X(n+1) = 17*X(n) + 0x5C93.
     * The GB oracle compares VM_RAND-driven actors tick by tick, so the WSC
     * platform hook must advance the same 16-bit state the same way. GBDK's
     * randw returns the new state with its bytes swapped (D is the low byte
     * and E the high byte of the SDCC return value). */
    __rand_seed = (UWORD)(__rand_seed * 17u + 0x5C93u);
    return (UWORD)((__rand_seed << 8) | (__rand_seed >> 8));
}
