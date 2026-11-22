// Placement probe: two 40 KiB far read-only sections and a far-pointer table.
#include <stdint.h>
#include <wonderful.h>
#include <ws.h>

#define PLACE_SIZE 40960

extern const uint8_t __far far_a[];
extern const uint8_t __far far_b[];
extern const uint8_t __far forced[];

const uint8_t __far *const far_table[2] = { far_a, far_b };

volatile uint16_t a_first;
volatile uint16_t a_last;
volatile uint16_t b_first;
volatile uint16_t b_last;

volatile uint16_t a_seg;
volatile uint16_t a_off;
volatile uint16_t b_seg;
volatile uint16_t b_off;
volatile uint16_t same_segment;
volatile uint16_t a_crosses;
volatile uint16_t b_crosses;
volatile uint16_t forced_seg;
volatile uint16_t forced_off;

__attribute__((noinline)) static void run(void) {
    a_first = far_table[0][0];
    a_last = far_table[0][PLACE_SIZE - 1];
    b_first = far_table[1][0];
    b_last = far_table[1][PLACE_SIZE - 1];

    a_seg = ws_ptr_segment(far_table[0]);
    a_off = ws_ptr_offset(far_table[0]);
    b_seg = ws_ptr_segment(far_table[1]);
    b_off = ws_ptr_offset(far_table[1]);
    same_segment = (a_seg == b_seg);

    a_crosses = ((uint32_t) a_off + PLACE_SIZE) > 0x10000UL;
    b_crosses = ((uint32_t) b_off + PLACE_SIZE) > 0x10000UL;

    forced_seg = ws_ptr_segment(forced);
    forced_off = ws_ptr_offset(forced);
}

void main(void) {
    run();
    while (1);
}
