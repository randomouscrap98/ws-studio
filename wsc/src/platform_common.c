/* Platform hooks shared by the WSC test image and product ROM. */

#include <stdint.h>

#include <wonderful.h>
#include <ws.h>

#include "vm.h"
#include "hal.h"
#include "d2c_scripts.h"
#include "d2c_manifest.h"

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

/* GBDK's rand state. The engine's save blob stores this exact variable, so a
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
