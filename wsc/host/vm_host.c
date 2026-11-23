/* Host platform hooks for the portable GBVM build. */

#include <stdint.h>

#include "vm.h"
#include "math.h"
#include "rand.h"

UWORD sys_time;

/* Converted scripts reach C RAM through the generated pointer table. */
UBYTE *vm_ram_ptr(UWORD idx) {
    return vm_ram_syms[idx];
}

void wait_vbl_done(void) {
}

UBYTE wait_frames(void * THIS, UBYTE start, UWORD * stack_frame) OLDCALL BANKED;

/* Native function operands are indexes into this table on the host. */
SCRIPT_UPDATE_FN vm_native_fns[] = {
    wait_frames,
};

static UWORD rng_state;

void initrand(UWORD seed) {
    rng_state = seed;
}

UWORD randw(void) {
    rng_state = (UWORD)(rng_state * 1103515245u + 12345u);
    return rng_state;
}

uint8_t isqrt(uint16_t x) {
    uint16_t result = 0;
    uint16_t bit = 0x8000;
    while (bit > x) bit >>= 2;
    while (bit) {
        if (x >= result + bit) {
            x -= result + bit;
            result = (result >> 1) + bit;
        } else {
            result >>= 1;
        }
        bit >>= 2;
    }
    return (uint8_t)result;
}

uint8_t atan2(int16_t y, int16_t x) {
    (void)y;
    (void)x;
    return 0;
}
