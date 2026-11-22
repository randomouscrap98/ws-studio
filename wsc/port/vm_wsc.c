/* WonderSwan Color platform hooks for the portable GBVM core. */

#include <stdbool.h>
#include <stdint.h>

#include <wonderful.h>
#include <ws.h>

#include "vm.h"
#include "math.h"
#include "rand.h"

/* One far const array per logical script bank. */
extern const uint8_t __far vmrom_bank0[];
extern const uint8_t __far vmrom_bank1[];

static const uint8_t __far *const vm_banks[] = {
    vmrom_bank0,
    vmrom_bank1,
};

const uint8_t __far *vm_bank_base(UBYTE bank) {
    return vm_banks[bank];
}

/* IRAM is the default data segment on the WonderSwan, so near addresses are
 * already system-RAM offsets. */
UBYTE *vm_ram_ptr(UWORD addr) {
    return (UBYTE *)addr;
}

UWORD sys_time;

UBYTE wait_frames(void * THIS, UBYTE start, UWORD * stack_frame) OLDCALL BANKED;

SCRIPT_UPDATE_FN vm_native_fns[] = {
    wait_frames,
};

/* Wait for the start of vertical blank; sys_time counts the waits. */
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
