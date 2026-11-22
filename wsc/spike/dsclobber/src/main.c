// Compiler hazard: a far dereference in a non-returning main() leaves %ds
// pointing at ROM, and the following global store is emitted DS-relative.
#include <stdint.h>
#include <wonderful.h>
#include <ws.h>

const uint8_t __far data[16] = {
    1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16,
};

volatile uint8_t idx;
volatile uint16_t before;
volatile uint16_t after;
volatile uint16_t data_seg;
volatile uint16_t data_off;

void main(void) {
    before = 0x1111;
    data_seg = ws_ptr_segment(data);
    data_off = ws_ptr_offset(data);
    after = 0xAAAA;

    // Volatile index prevents constant folding of this far read.
    uint8_t x = data[idx];

    // Expected C semantics: 0x2223.  With the current compiler the store
    // goes through the ROM segment left in %ds, so the pre-read 0xAAAA stays.
    after = 0x2222 + x;
    while (1);
}
