// Segment-boundary probe: walk a 96 KiB far section with ordinary p++.
#include <stdint.h>
#include <wonderful.h>
#include <ws.h>

#define BIG_SIZE 0x18000UL

extern const uint8_t __far big[];

volatile uint32_t mismatch_at;
volatile uint32_t wrap_at;
volatile uint16_t seg_before;
volatile uint16_t off_before;
volatile uint16_t seg_after;
volatile uint16_t off_after;
volatile uint16_t first_byte;
volatile uint16_t wrapped_index_byte;
volatile uint16_t norm_0;
volatile uint16_t norm_8000;
volatile uint16_t norm_ffff;
volatile uint16_t norm_10000;
volatile uint16_t norm_end;

// Rebuild a far pointer when the 16-bit offset would overflow.  The old
// compiler narrows 32-bit arithmetic here, so do it in segment:offset form.
static uint8_t __far *advance_far(uint16_t seg, uint16_t off, uint32_t delta) {
    return (uint8_t __far *) MK_FP(seg + (uint16_t) (delta >> 4),
                                   off + (uint16_t) (delta & 0x0F));
}

__attribute__((noinline)) static void run(void) {
    const uint8_t __far *p = big;
    uint32_t i;

    seg_before = ws_ptr_segment(p);
    off_before = ws_ptr_offset(p);
    wrap_at = 0x10000UL - off_before;
    first_byte = big[0];

    // A constant index >= 64 KiB is truncated into the pointer's offset.
    wrapped_index_byte = big[BIG_SIZE - 1];

    // The same bytes, addressed with an explicitly re-based far pointer.
    norm_0 = *advance_far(seg_before, off_before, 0);
    norm_8000 = *advance_far(seg_before, off_before, 0x8000UL);
    norm_ffff = *advance_far(seg_before, off_before, 0xFFFFUL);
    norm_10000 = *advance_far(seg_before, off_before, 0x10000UL);
    norm_end = *advance_far(seg_before, off_before, BIG_SIZE - 1);

    mismatch_at = 0xFFFFFFFFUL;
    for (i = 0; i < BIG_SIZE; i++) {
        uint8_t expected = 0x11 * (uint8_t) (i / 0x4000UL + 1);
        if (*p != expected) {
            mismatch_at = i;
            break;
        }
        p++;
    }

    seg_after = ws_ptr_segment(p);
    off_after = ws_ptr_offset(p);
}

void main(void) {
    run();
    while (1);
}
