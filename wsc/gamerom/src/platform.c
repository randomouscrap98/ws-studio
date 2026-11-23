/* WSC platform hooks for the portable GBVM core on the boot ROM. */

#include <stdbool.h>
#include <stdint.h>

#include <wonderful.h>
#include <ws.h>

#include "vm.h"
#include "hal.h"
#include "d2c_scripts.h"
#include "d2c_manifest.h"

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
