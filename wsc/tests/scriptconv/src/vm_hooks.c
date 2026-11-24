/* WSC platform hooks for the converted-script test. */

#include <stdbool.h>
#include <stdint.h>

#include <wonderful.h>
#include <ws.h>

#include "vm.h"
#include "math.h"
#include "rand.h"
#include "s2c_test.h"

static const uint8_t __far *const vm_banks[] = {
    (const uint8_t __far *)0,
    s2c_bank1,
    s2c_bank2,
};

const uint8_t __far *vm_bank_base(UBYTE bank) {
    return vm_banks[bank];
}

/* C objects referenced by the converted test script's index tables. */
UBYTE s2c_ram_i8;
UWORD s2c_ram_i16;
UBYTE s2c_ram_bytes[2] = { 0x11, 0x22 };
const UBYTE __far s2c_far_data[] __attribute__((aligned(2))) = { 0x9C, 0x34, 0x12 };

UBYTE *vm_ram_ptr(UWORD idx) {
    return vm_ram_syms[idx];
}

UWORD sys_time;

UBYTE wait_frames(void * THIS, UBYTE start, UWORD * stack_frame) OLDCALL BANKED;

SCRIPT_UPDATE_FN vm_native_fns[] = {
    wait_frames,
};

void wait_vbl_done(void) {
    while (ws_display_get_current_line() >= WS_DISPLAY_HEIGHT_PIXELS) {
    }
    while (ws_display_get_current_line() < WS_DISPLAY_HEIGHT_PIXELS) {
    }
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
