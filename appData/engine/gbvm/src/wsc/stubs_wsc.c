/* WonderSwan Color engine stubs.
 *
 * These are the subsystems the C11 boot path does not need: audio, SIO,
 * saving, UI/dialogue and the GB interrupt/LCD plumbing. Each group is a
 * deliberate no-op so the real scene, actor, scroll and camera code can run.
 */

#include <stdint.h>

#include "gbdk/platform.h"
#include "gbs_types.h"
#include "palette.h"
#include "fade_manager.h"
#include "ui.h"
#include "interrupts.h"
#include "parallax.h"
#include "load_save.h"
#include "sio.h"
#include "events.h"
#include "hal.h"

/* ---- GB register names referenced by the shared engine sources ---- */
UBYTE _is_GBA;
volatile UBYTE _cpu = CGB_TYPE;
volatile UBYTE LCDC_REG;
volatile UBYTE STAT_REG;
volatile UBYTE LYC_REG;
volatile UBYTE WX_REG;
volatile UBYTE WY_REG;
volatile UBYTE IE_REG;
volatile UBYTE BGP_REG;
volatile UBYTE OBP0_REG;
volatile UBYTE OBP1_REG;
volatile UBYTE TMA_REG;
volatile UBYTE TAC_REG;
volatile UBYTE _current_bank;
volatile UBYTE __current_bank;

/* Platform variables named by the script converter but not assigned by
 * script_engine_init.s in this project. */
WORD plat_vel_y;
UBYTE plat_next_state;

/* ---- data symbols named by the script converter ---- */
uint8_t DIV_REG[4];
uint8_t __mute_mask_sound_gbstudio_sfx_sav_00[4];
uint8_t __mute_mask_sound_gbstudio_sfx_sav_03[4];
uint8_t __mute_mask_sound_gbstudio_sfx_sav_04[4];
uint8_t __mute_mask_sound_gbstudio_sfx_sav_05[4];
uint8_t __mute_mask_sound_gbstudio_sfx_sav_07[4];
uint8_t __mute_mask_sound_gbstudio_sfx_sav_09[4];
uint8_t __mute_mask_sound_legacy_0[4];

/* absolute.c stores this at a fixed GB WRAM address; on WSC it is ordinary
 * RAM used by palette.c and the (stubbed) fade code. */
palette_entry_t BkgPalette[8];

/* ---- display hooks ---- */
void display_off(void) {
    hal_display_off();
}

void cpu_fast(void) {
}

void add_VBL(void (*isr)(void)) {
    (void)isr;
}

void add_LCD(void (*isr)(void)) {
    (void)isr;
}

/* ---- interrupt / LCD ISR stubs ---- */
UBYTE hide_sprites;
UBYTE show_actors_on_overlay;

void remove_LCD_ISRs(void) {
}

void simple_LCD_isr(void) {
}

void fullscreen_LCD_isr(void) {
}

void VBL_isr(void) {
}

/* ---- parallax stub (the scenes on this path have no parallax rows) ---- */
parallax_row_t parallax_rows[3];
parallax_row_t *parallax_row;

void parallax_init(void) {
    parallax_rows[0].next_y = 0;
    parallax_rows[0].scx = 0;
    parallax_rows[0].shift = 0;
    parallax_rows[0].start_tile = 0;
    parallax_rows[0].tile_height = 0;
    parallax_rows[0].shadow_scx = 0;
}

void parallax_LCD_isr(void) {
}

/* ---- audio driver stub ---- */
volatile UBYTE NR50_REG;
volatile unsigned char hUGE_mute_mask;
uint8_t music_mute_mask;
uint8_t music_effective_mute;
uint8_t music_global_mute_mask;
script_event_t music_events[4];

void music_init_driver(void) {
}

void music_init_events(uint8_t preserve) {
    (void)preserve;
}

void music_events_update(void) {
}

uint8_t music_events_poll(void) {
    return 0;
}

void hUGETrackerRoutine(unsigned char tick, unsigned int param) {
    (void)tick;
    (void)param;
}

/* ---- serial link stub ---- */
void SIO_init(void) {
}

/* ---- save stub ---- */
void data_init(void) {
}

void data_save(UBYTE slot) {
    (void)slot;
}

UBYTE data_load(UBYTE slot) {
    (void)slot;
    return FALSE;
}

void data_clear(UBYTE slot) {
    (void)slot;
}

UBYTE data_peek(UBYTE slot, UINT16 idx, UWORD count, UINT16 *dest) {
    (void)slot;
    (void)idx;
    (void)count;
    (void)dest;
    return 0;
}

/* ---- UI / dialogue: the real ui.c now provides the overlay window ---- */
/* ---- fade stub: palettes stay fully visible ---- */
UBYTE fade_running;
UBYTE fade_frames_per_step;
UBYTE fade_black;
UBYTE fade_timer;
UBYTE fade_style;

void fade_init(void) {
    fade_running = FALSE;
    fade_frames_per_step = 0;
    fade_black = FALSE;
    fade_timer = 0;
    fade_style = 0;
}

void fade_in(void) {
}

void fade_out(void) {
}

void fade_update(void) {
}

void fade_applypalettechange(void) {
}

void fade_setspeed(UBYTE speed) {
    (void)speed;
}

void fade_in_modal(void) {
}

void fade_out_modal(void) {
}
