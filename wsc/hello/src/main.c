// SPDX-License-Identifier: CC0-1.0
#include <stdint.h>
#include <wonderful.h>
#include <ws.h>

volatile uint16_t hello_magic;

void main(void) {
	hello_magic = 0x1234;

	ws_system_set_mode(WS_MODE_COLOR_4BPP);

	/* Backdrop uses palette 0, index 1; make that entry pure red. */
	WS_SCREEN_COLOR_MEM(0)[1] = WS_RGB(15, 0, 0);
	outportb(WS_DISPLAY_BACK_PORT, 0x01);

	/* No tiles or sprites: only the backdrop is visible. */
	ws_display_set_control(0);

	while (1);
}
