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

/* wsrun patches the byte after this magic in the ROM image before boot. */
const volatile __far uint8_t wsc_boot_slot[8] = {
    'W', 'S', 'C', 'B', 'O', 'O', 'T', 0
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
};

/* Called by the generated bootstrap before the first scene is loaded. */
void wsc_boot_select(far_ptr_t *scene, INT16 *x, INT16 *y) {
    UBYTE id = wsc_boot_slot[7];
    const struct boot_entry __far *entry;

    if (id >= BOOT_SCENE_COUNT) id = 0;
    entry = &boot_table[id];
    scene->bank = 0;
    scene->ptr = entry->scene;
    *x = entry->x;
    *y = entry->y;
}

/* One far const array per converted script bank. */
static const uint8_t __far *const vm_banks[D2C_BANK_COUNT] = {
    D2C_BANK_LIST
};

const uint8_t __far *vm_bank_base(UBYTE bank) {
    return (bank < D2C_BANK_COUNT) ? vm_banks[bank] : vm_banks[0];
}

UBYTE *vm_ram_ptr(UWORD idx) {
    return vm_ram_syms[idx];
}

UWORD sys_time;

UBYTE wait_frames(void *THIS, UBYTE start, UWORD *stack_frame)
    OLDCALL BANKED;

SCRIPT_UPDATE_FN vm_native_fns[] = {
    wait_frames,
};

void wait_vbl_done(void) {
    hal_wait_vblank();
    sys_time++;
}

static UWORD rng_state;

void initrand(UWORD seed) {
    rng_state = seed;
}

UWORD randw(void) {
    rng_state = (UWORD)(rng_state * 1103515245u + 12345u);
    return rng_state;
}
