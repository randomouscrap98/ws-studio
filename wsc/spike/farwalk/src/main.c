// Far-pointer feature probe: walk, function argument, struct member, table.
#include <stdint.h>
#include <wonderful.h>
#include <ws.h>

#define N 32

const uint8_t __far far_data[N] = {
    0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15,
    16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31,
};

typedef struct {
    const uint8_t __far *ptr;
    uint16_t len;
} far_view;

static far_view view = { far_data, 16 };

static const uint8_t __far *const far_table[2] = { far_data, far_data + 16 };

volatile uint16_t sum_direct;
volatile uint16_t sum_param;
volatile uint16_t sum_struct;
volatile uint16_t sum_table;

volatile uint16_t start_seg;
volatile uint16_t start_off;
volatile uint16_t end_seg;
volatile uint16_t end_off;
volatile uint16_t tbl_seg_delta;
volatile uint16_t tbl_off_delta;

static uint16_t sum_far(const uint8_t __far *p, uint16_t len) {
    uint16_t sum = 0;
    while (len--) sum += *p++;
    return sum;
}

// Far dereferences dirty %ds.  Keeping this out of a non-returning main()
// lets the compiler emit %ss-relative accesses and restore %ds on return.
__attribute__((noinline)) static void run(void) {
    const uint8_t __far *p = far_data;
    uint16_t i;
    uint16_t sum = 0;

    start_seg = ws_ptr_segment(p);
    start_off = ws_ptr_offset(p);

    for (i = 0; i < 16; i++) sum += *p++;
    sum_direct = sum;

    end_seg = ws_ptr_segment(p);
    end_off = ws_ptr_offset(p);

    sum_param = sum_far(far_data + 16, 16);
    sum_struct = sum_far(view.ptr, view.len);

    sum = 0;
    for (i = 0; i < view.len; i++) sum += far_table[0][i];
    for (i = 0; i < view.len; i++) sum += far_table[1][i];
    sum_table = sum;

    tbl_seg_delta = ws_ptr_segment(far_table[1]) - ws_ptr_segment(far_table[0]);
    tbl_off_delta = ws_ptr_offset(far_table[1]) - ws_ptr_offset(far_table[0]);
}

void main(void) {
    run();
    while (1);
}
