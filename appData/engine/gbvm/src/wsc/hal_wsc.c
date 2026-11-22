/* WonderSwan Color HAL: display, vblank, input and scrolling. */
#include <stdint.h>
#include <wonderful.h>
#include <ws.h>
#include "hal.h"
#include "hal_wsc_internal.h"

uint8_t hal_screen_w;
uint8_t hal_screen_h;
uint16_t hal_screen_w_px;
uint16_t hal_screen_h_px;

static volatile uint16_t hal_vblanks;

/* Screen 1 is 32x32 cells; the hardware needs it 2 KiB aligned. */
volatile ws_screen_t hal_screen
    __attribute__((section(".iramx_screen"), aligned(0x800)));

static void __attribute__((interrupt)) hal_vblank_isr(void) {
    hal_vblanks++;
    ws_int_ack(WS_INT_ACK_VBLANK);
}

void hal_display_init(void) {
    uint16_t i;

    ws_display_set_control(0);
    ws_system_set_mode(WS_MODE_COLOR_4BPP);

    hal_screen_w = WS_DISPLAY_WIDTH_TILES;
    hal_screen_h = WS_DISPLAY_HEIGHT_TILES;
    hal_screen_w_px = WS_DISPLAY_WIDTH_PIXELS;
    hal_screen_h_px = WS_DISPLAY_HEIGHT_PIXELS;

    ws_display_set_screen1_address((const void __wf_iram *)&hal_screen);
    ws_display_scroll_screen1_to(0, 0);
    outportb(WS_DISPLAY_BACK_PORT, 0x00);

    for (i = 0; i < WS_SCREEN_WIDTH_TILES * WS_SCREEN_HEIGHT_TILES; i++)
        hal_screen.cell[i] = 0;

    ws_int_set_handler(WS_INT_VBLANK, (void __far *)hal_vblank_isr);
    ws_int_enable(WS_INT_ENABLE_VBLANK);
    ia16_enable_irq();
}

void hal_display_on(void) {
    ws_display_set_control(WS_DISPLAY_CTRL_SCR1_ENABLE);
}

void hal_display_off(void) {
    ws_display_set_control(0);
}

uint16_t hal_vblank_count(void) {
    return hal_vblanks;
}

void hal_wait_vblank(void) {
    uint16_t start = hal_vblanks;
    while (hal_vblanks == start)
        ia16_halt();
}

uint8_t hal_input_read(void) {
    uint16_t keys = ws_keypad_scan();
    uint8_t joy = 0;

    if (keys & WS_KEY_X1) joy |= J_UP;
    if (keys & WS_KEY_X2) joy |= J_RIGHT;
    if (keys & WS_KEY_X3) joy |= J_DOWN;
    if (keys & WS_KEY_X4) joy |= J_LEFT;
    if (keys & WS_KEY_A) joy |= J_A;
    if (keys & WS_KEY_B) joy |= J_B;
    if (keys & WS_KEY_START) joy |= J_START;

    return joy;
}

void hal_scroll_to(int16_t x, int16_t y) {
    ws_display_scroll_screen1_to((uint8_t)x, (uint8_t)y);
}
