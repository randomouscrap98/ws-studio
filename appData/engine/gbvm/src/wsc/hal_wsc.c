/* WonderSwan Color HAL: display, vblank, input and scrolling. */
#include <stdint.h>
#include <string.h>
#include <wonderful.h>
#include <ws.h>
#include "hal.h"
#include "hal_wsc_internal.h"
#include "wsc_tiles.h"

uint8_t hal_screen_w;
uint8_t hal_screen_h;
uint16_t hal_screen_w_px;
uint16_t hal_screen_h_px;

static volatile uint16_t hal_vblanks;

static uint8_t hal_win_x;
static uint8_t hal_win_y;
static uint8_t hal_win_visible;
static uint8_t hal_win_palette;

uint8_t hal_win_tiles[WS_SCREEN_WIDTH_TILES * WS_SCREEN_HEIGHT_TILES];
uint8_t hal_win_attrs[WS_SCREEN_WIDTH_TILES * WS_SCREEN_HEIGHT_TILES];

/* Global tile offset applied by the GB map writers (vm_overlay_set_map). */
volatile uint8_t _map_tile_offset;

/* Screens 1 and 2 are 32x32 cells; the hardware needs them 2 KiB aligned. */
volatile ws_screen_t hal_screen
    __attribute__((section(".iramx_screen"), aligned(0x800)));
volatile ws_screen_t hal_win_screen
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
    ws_display_set_screen2_address((const void __wf_iram *)&hal_win_screen);
    ws_display_scroll_screen1_to(0, 0);
    ws_display_scroll_screen2_to(0, 0);
    outportb(WS_DISPLAY_BACK_PORT, 0x00);

    for (i = 0; i < WS_SCREEN_WIDTH_TILES * WS_SCREEN_HEIGHT_TILES; i++) {
        hal_screen.cell[i] = 0;
        hal_win_screen.cell[i] = 0;
    }
    hal_win_visible = 0;
    hal_win_x = 0;
    hal_win_y = 0;

    ws_int_set_handler(WS_INT_VBLANK, (void __far *)hal_vblank_isr);
    ws_int_enable(WS_INT_ENABLE_VBLANK);
    ia16_enable_irq();
}

void hal_display_on(void) {
    uint8_t control = WS_DISPLAY_CTRL_SCR1_ENABLE |
                      WS_DISPLAY_CTRL_SPR_ENABLE;

    if (hal_win_visible)
        control |= WS_DISPLAY_CTRL_SCR2_ENABLE |
                   WS_DISPLAY_CTRL_SCR2_WIN_INSIDE;
    ws_display_set_control(control);
}

void hal_display_off(void) {
    ws_display_set_control(0);
}

void hal_window_hide(void) {
    uint8_t control = ws_display_get_control();

    control &= (uint8_t)~(WS_DISPLAY_CTRL_SCR2_ENABLE |
                          WS_DISPLAY_CTRL_SCR2_WIN_MASK);
    ws_display_set_control(control);
    hal_win_visible = 0;
}

void hal_window_set(int16_t x, int16_t y) {
    uint8_t control;

    if (x < 0 || y < 0 || x >= hal_screen_w_px || y >= hal_screen_h_px) {
        hal_window_hide();
        return;
    }

    ws_display_set_screen2_window((uint8_t)x, (uint8_t)y,
                                  (uint8_t)(hal_screen_w_px - x),
                                  (uint8_t)(hal_screen_h_px - y));
    /* Screen 2 has a fixed origin.  Scrolling it by -x/-y puts window-map
     * cell (0, 0) at the window's top-left corner, as on the GB. */
    ws_display_scroll_screen2_to((uint8_t)(-x), (uint8_t)(-y));

    control = ws_display_get_control();
    control |= WS_DISPLAY_CTRL_SCR2_ENABLE |
               WS_DISPLAY_CTRL_SCR2_WIN_INSIDE;
    ws_display_set_control(control);

    hal_win_x = (uint8_t)x;
    hal_win_y = (uint8_t)y;
    hal_win_visible = 1;
    hal_window_flush();
}

uint8_t hal_window_visible(void) {
    return hal_win_visible;
}

uint8_t hal_window_x(void) {
    return hal_win_x;
}

uint8_t hal_window_y(void) {
    return hal_win_y;
}

void hal_window_set_palette(uint8_t palette) {
    hal_win_palette = palette;
}

void hal_window_reset(void) {
    memset(hal_win_tiles, 0, sizeof(hal_win_tiles));
    memset(hal_win_attrs, HAL_WIN_UI_ATTR, sizeof(hal_win_attrs));
}

void hal_window_flush(void) {
    uint16_t i;

    for (i = 0; i < WS_SCREEN_WIDTH_TILES * WS_SCREEN_HEIGHT_TILES; i++) {
        uint8_t attr = hal_win_attrs[i];
        uint16_t index = hal_win_tiles[i];

        uint16_t cell = WS_SCREEN_ATTR_TILE_EX(index);
        if (attr & HAL_WIN_BANK1)
            cell |= WS_SCREEN_ATTR_BANK(1);

        if (attr & HAL_WIN_UI_ATTR) {
            cell |= WS_SCREEN_ATTR_PALETTE(hal_win_palette);
        } else {
            cell |= WS_SCREEN_ATTR_PALETTE(attr & 0x07);
            if (attr & 0x20)
                cell |= WS_SCREEN_ATTR_FLIP_H;
            if (attr & 0x40)
                cell |= WS_SCREEN_ATTR_FLIP_V;
        }
        hal_win_screen.cell[i] = cell;
    }
}

void hal_win_map_put(uint8_t x, uint8_t y, uint8_t w, uint8_t h,
                     const uint8_t __far *map,
                     const uint8_t __far *attrs, uint8_t map_w) {
    uint8_t row, col;

    for (row = 0; row < h; row++) {
        for (col = 0; col < w; col++) {
            uint16_t dst = (((uint16_t)y + row) & 31) * 32 +
                           (((uint16_t)x + col) & 31);
            uint16_t src = (uint16_t)row * map_w + col;

            hal_win_tiles[dst] = (uint8_t)(map[src] + _map_tile_offset);
            hal_win_attrs[dst] = attrs ? attrs[src] : 0;
        }
    }
}

uint16_t hal_vblank_count(void) {
    return hal_vblanks;
}

void hal_wait_vblank(void) {
    uint16_t start = hal_vblanks;
    while (hal_vblanks == start)
        ia16_halt();
    /* A libretro ``retro_run`` ends a few hundred cycles after the vblank
     * interrupt, so work started right after the wait races with the frame
     * boundary.  Wait for the first line after vblank, which is past that
     * boundary, so input reads always happen at a fixed point in the frame. */
    while (ws_display_get_current_line() == WS_DISPLAY_HEIGHT_PIXELS)
        ;
}

/* WSC keypad bits to GB J_* bits, including Y1 -> Select. */
uint8_t hal_input_read(void) {
    static const struct {
        uint16_t ws_key;
        uint8_t j_mask;
    } map[] = {
        { WS_KEY_X1, J_UP },
        { WS_KEY_X2, J_RIGHT },
        { WS_KEY_X3, J_DOWN },
        { WS_KEY_X4, J_LEFT },
        { WS_KEY_A, J_A },
        { WS_KEY_B, J_B },
        { WS_KEY_START, J_START },
        { WS_KEY_Y1, J_SELECT },
    };
    uint16_t keys = ws_keypad_scan();
    uint8_t mask = 0;
    uint16_t i;

    for (i = 0; i < sizeof(map) / sizeof(map[0]); i++) {
        if (keys & map[i].ws_key)
            mask |= map[i].j_mask;
    }
    return mask;
}

void hal_scroll_to(int16_t x, int16_t y) {
    ws_display_scroll_screen1_to((uint8_t)x, (uint8_t)y);
}
