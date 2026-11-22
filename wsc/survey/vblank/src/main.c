/* C05s: prove a libws vblank interrupt fires under wsrun. */
#include <stdint.h>
#include <wonderful.h>
#include <ws.h>

volatile uint16_t vblank_count;
volatile uint16_t vblank_last_count;
volatile uint16_t main_loops;

static void __attribute__((interrupt)) vblank_handler(void) {
    vblank_count++;
    ws_int_ack(WS_INT_ACK_VBLANK);
}

void main(void) {
    ws_int_set_handler(WS_INT_VBLANK, (void __far *) vblank_handler);
    ws_int_enable(WS_INT_ENABLE_VBLANK);
    ia16_enable_irq();

    while (1) {
        main_loops++;
        vblank_last_count = vblank_count;
        ia16_halt();
    }
}
