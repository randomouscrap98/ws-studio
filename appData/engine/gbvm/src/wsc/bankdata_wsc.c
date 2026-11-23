/* WonderSwan Color banked-data helpers.
 *
 * GB Studio's helpers switch a ROM bank and then read through a near pointer.
 * On WSC the data pointers are full far pointers and no bank register is
 * involved, so the bank argument is informational only. Writes that load
 * hardware tiles still go through the HAL, which performs the GB-to-WSC tile
 * conversion.
 */

#include <stdint.h>
#include <string.h>

#include "gbdk/platform.h"
#include "compat.h"
#include "bankdata.h"
#include "hal.h"
#include "hal_wsc_internal.h"

void SetBankedBkgData(UBYTE i, UBYTE l, const unsigned char __far *ptr,
                      UBYTE bank) {
    (void)bank;
    hal_load_bkg_tiles(i, l, ptr, 2);
}

void SetBankedSpriteData(UBYTE i, UBYTE l, const unsigned char __far *ptr,
                         UBYTE bank) {
    (void)bank;
    hal_load_sprite_tiles(i, l, ptr, 2);
}

void SetBankedBkgTiles(UINT8 x, UINT8 y, UINT8 w, UINT8 h,
                       const unsigned char __far *tiles, UBYTE bank) {
    (void)bank;
    hal_put_bkg_tiles(x, y, w, h, tiles, NULL, w);
}

void SetBankedWinTiles(UINT8 x, UINT8 y, UINT8 w, UINT8 h,
                       const unsigned char __far *tiles, UBYTE bank) {
    (void)bank;
    hal_put_win_tiles(x, y, w, h, tiles, NULL, w);
}

void ReadBankedFarPtr(far_ptr_t *dest, const void __far *ptr, UBYTE bank) {
    (void)bank;
    *dest = *(const far_ptr_t __far *)ptr;
}

UWORD ReadBankedUWORD(const void __far *ptr, UBYTE bank) {
    const UBYTE __far *bytes = (const UBYTE __far *)ptr;
    (void)bank;
    /* Bytewise: the source address is not guaranteed to be word aligned. */
    return (UWORD)(bytes[0] | ((UWORD)bytes[1] << 8));
}

void MemcpyBanked(void *to, const void __far *from, size_t n, UBYTE bank) {
    UBYTE *dst = (UBYTE *)to;
    const UBYTE __far *src = (const UBYTE __far *)from;
    (void)bank;
    while (n--)
        *dst++ = *src++;
}

void MemcpyVRAMBanked(void *to, const void __far *from, size_t n, UBYTE bank) {
    /* WSC VRAM is not part of the CPU address space; callers that write real
     * VRAM use the HAL. Keep the helper usable as a far-to-near copy. */
    MemcpyBanked(to, from, n, bank);
}

UBYTE IndexOfFarPtr(const far_ptr_t __far *list, UBYTE bank, UBYTE count,
                    const far_ptr_t *item) {
    UBYTE i;
    (void)bank;
    for (i = 0; i != count; i++) {
        const far_ptr_t __far *entry = list + i;
        if ((entry->bank == item->bank) && (entry->ptr == item->ptr))
            return i;
    }
    return count;
}
