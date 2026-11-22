// Reach probe: read the first and last byte of 12 far chunks, each in its
// own 64 KiB linear bank, with no ROM bank-register writes.
#include <stdint.h>
#include <wonderful.h>
#include <ws.h>

#define CHUNK_SIZE 0xFC00
#define CHUNK_COUNT 12

extern const uint8_t __far chunk0[];
extern const uint8_t __far chunk1[];
extern const uint8_t __far chunk2[];
extern const uint8_t __far chunk3[];
extern const uint8_t __far chunk4[];
extern const uint8_t __far chunk5[];
extern const uint8_t __far chunk6[];
extern const uint8_t __far chunk7[];
extern const uint8_t __far chunk8[];
extern const uint8_t __far chunk9[];
extern const uint8_t __far chunk10[];
extern const uint8_t __far chunk11[];

const uint8_t __far *const chunks[CHUNK_COUNT] = {
    chunk0, chunk1, chunk2, chunk3, chunk4, chunk5, chunk6, chunk7, chunk8, chunk9, chunk10, chunk11
};

volatile uint16_t chunk_ok;
volatile uint16_t firsts_sum;
volatile uint16_t lasts_sum;
volatile uint16_t chunk_segs[CHUNK_COUNT];
volatile uint16_t bank_c0;

__attribute__((noinline)) static void run(void) {
    uint16_t i;
    chunk_ok = 0;
    firsts_sum = 0;
    lasts_sum = 0;
    for (i = 0; i < CHUNK_COUNT; i++) {
        uint8_t first = chunks[i][0];
        uint8_t last = chunks[i][CHUNK_SIZE - 1];
        firsts_sum += first;
        lasts_sum += last;
        chunk_segs[i] = ws_ptr_segment(chunks[i]);
        if (first == (uint8_t) (0x80 + i) && last == (uint8_t) (0x7F - i)) {
            chunk_ok++;
        }
    }
    bank_c0 = inportb(0xC0);
}

void main(void) {
    run();
    while (1);
}
