/* WonderSwan Color parallax band scroll.
 *
 * The GB build keeps its LYC ISR in parallax.c.  WSC has a line-match
 * interrupt (WS_INT_LINE_MATCH) and separate screen-1 scroll registers, so
 * the same band walk is done here in C.  The band's next_y is a GB screen
 * line (0..143); the WSC display is also 144 lines high, so the lines map
 * one to one.  Each write only changes screen 1: screen 2 (the overlay
 * window) and the sprite layer keep their own scroll.
 *
 * A 160 px logical screen is centred with a 32 px physical left margin, so
 * the horizontal scroll is shifted by the same origin as hal_scroll_to().
 */

#include <stdint.h>
#include <string.h>

#include <wonderful.h>
#include <ws.h>

#include "parallax.h"
#include "scroll.h"
#include "hal.h"

parallax_row_t parallax_rows[3];
parallax_row_t *parallax_row;

static const parallax_row_t parallax_rows_defaults[3] = {
    PARALLAX_STEP(0, 2, 2),
    PARALLAX_STEP(2, 4, 1),
    PARALLAX_STEP(4, 0, 0)
};

void parallax_init(void) {
    memcpy(parallax_rows, parallax_rows_defaults, sizeof(parallax_rows));
    parallax_row = parallax_rows;
}

/* The engine checks this pointer identity in add_LCD(); the hardware entry
 * point is parallax_line_isr. */
void parallax_LCD_isr(void) {
}

static void __attribute__((interrupt)) parallax_line_isr(void) {
    parallax_row_t *row = parallax_row;
    uint8_t next_y = row->next_y;
    uint8_t scx = row->scx;
    /* The last band scrolls vertically with the camera; the upper bands stay
     * at the top of the map, as on the GB. */
    uint8_t scy = next_y ? 0 : (uint8_t)draw_scroll_y;

    ws_int_ack(WS_INT_ACK_LINE_MATCH);
    outportb(WS_DISPLAY_LINE_IRQ_PORT, next_y);
    hal_scroll_screen1_to((int16_t)(scx - hal_screen_origin_x()), scy);

    if (next_y)
        parallax_row = row + 1;
    else
        parallax_row = parallax_rows;
}

/* Runs from the vblank ISR: publish the scroll values scroll_viewport()
 * computed during the frame, and rewind the band walk. */
void hal_parallax_vblank(void) {
    scroll_shadow_update();
    parallax_row = parallax_rows;
}

void hal_parallax_enable(void) {
    parallax_row = parallax_rows;
    ws_int_set_handler(WS_INT_LINE_MATCH, (void __far *)parallax_line_isr);
    outportb(WS_DISPLAY_LINE_IRQ_PORT, 0);
    ws_int_ack(WS_INT_ACK_LINE_MATCH);
    ws_int_enable(WS_INT_ENABLE_LINE_MATCH);
}

void hal_parallax_disable(void) {
    ws_int_disable(WS_INT_ENABLE_LINE_MATCH);
    ws_int_ack(WS_INT_ACK_LINE_MATCH);
    parallax_row = parallax_rows;
}
