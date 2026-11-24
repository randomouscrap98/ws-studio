/* WonderSwan Color cartridge SRAM access for the engine save path.
 *
 * The WSC maps external cartridge RAM linearly at 0x10000 (segment 0x1000).
 * A 32 KiB SRAM cart occupies the first half of the 64 KiB RAM bank 0, so
 * the engine's four 8 KiB save banks are offsets 0x0000, 0x2000, 0x4000 and
 * 0x6000 inside that window.  The RAM bank port still has to point at bank
 * 0; there is no separate SRAM enable register.
 */
#include <stdint.h>

#include <wonderful.h>
#include <ws.h>

#include "hal.h"

#define HAL_SRAM_BANK_SIZE 0x2000u
#define HAL_SRAM_BANK_COUNT 4u

void hal_sram_init(void) {
    ws_bank_ram_set(0);
}

uint8_t FAR *hal_sram_select(uint8_t bank) {
    if (bank >= HAL_SRAM_BANK_COUNT)
        return (uint8_t FAR *)0;
    return WS_SRAM_MEM + (uint16_t)(bank * HAL_SRAM_BANK_SIZE);
}

void hal_sram_copy_to(uint8_t FAR *dst, const uint8_t *src, uint16_t len) {
    while (len--)
        *dst++ = *src++;
}

void hal_sram_copy_from(uint8_t *dst, const uint8_t FAR *src, uint16_t len) {
    while (len--)
        *dst++ = *src++;
}
