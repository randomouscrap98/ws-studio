// SPDX-License-Identifier: CC0-1.0
#include <stdint.h>
#include <wonderful.h>
#include <ws.h>

volatile uint16_t echo_keys;
volatile uint8_t echo_ready;

void main(void) {
	ws_system_set_mode(WS_MODE_COLOR_4BPP);

	/* Backdrop uses palette 0, index 1; make that entry green. */
	WS_SCREEN_COLOR_MEM(0)[1] = WS_RGB(0, 15, 0);
	outportb(WS_DISPLAY_BACK_PORT, 0x01);

	/* No tiles or sprites: only the backdrop is visible. */
	ws_display_set_control(0);

	echo_ready = 1;
	while (1)
		echo_keys = ws_keypad_scan();
}
