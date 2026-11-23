#ifndef __MUSIC_MANAGER_WSC_H_INCLUDE__
#define __MUSIC_MANAGER_WSC_H_INCLUDE__

/* WonderSwan Color music manager: the audio chunk fills in these stubs.
 *
 * The engine calls the same names as on the Game Boy, but the WSC build has
 * no GBT/hUGE player yet.  These inline bodies are deliberate no-ops so the
 * VM, scene and UI paths link and run without touching GB sound registers. */

#include "events.h"
#include "sfx_player.h"

#include "hUGEDriver.h"

#define TRACK_T hUGESong_t

extern script_event_t music_events[4];

#define MUSIC_SFX_PRIORITY_MINIMAL  0
#define MUSIC_SFX_PRIORITY_NORMAL   4
#define MUSIC_SFX_PRIORITY_HIGH     8

#define MUSIC_STOP_BANK SFX_STOP_BANK

extern volatile uint8_t music_current_track_bank;
extern uint8_t music_mute_mask;
extern uint8_t music_effective_mute;
extern const TRACK_T FAR * music_next_track;
extern const TRACK_T FAR * music_current_track;
extern uint8_t music_global_mute_mask;
extern uint8_t music_sfx_priority;

void music_init_driver(void) BANKED;

void music_init_events(uint8_t preserve) BANKED;
void music_events_update(void) NONBANKED;
uint8_t music_events_poll(void) BANKED;

void music_play_isr(void);
void music_pause(uint8_t pause);

#define MUSIC_CH_1 SFX_CH_1
#define MUSIC_CH_2 SFX_CH_2
#define MUSIC_CH_3 SFX_CH_3
#define MUSIC_CH_4 SFX_CH_4

#define MUTE_MASK_NONE 0
#define MUTE_MASK_WAVE MUSIC_CH_3

inline void driver_init(uint8_t bank, const TRACK_T FAR * track, uint8_t loop) {
    (void)bank; (void)track; (void)loop;
}

inline void driver_update(void) {
}

inline void driver_reset_wave(void) {
}

inline uint8_t driver_set_mute_mask(uint8_t mute_mask) {
    return mute_mask;
}

inline void music_setpos(UBYTE pattern, UBYTE row) {
    (void)pattern; (void)row;
}

inline void music_load(uint8_t bank, const TRACK_T FAR * data) {
    (void)bank; (void)data;
}

inline void music_stop(void) {
}

inline void music_sound_cut(void) {
}

inline uint8_t music_sound_cut_mask(uint8_t mask) {
    return mask;
}

inline void music_setup_timer(void) {
}

inline void music_init(void) {
}

inline void music_play_sfx(uint8_t bank, const uint8_t FAR * sample,
                           uint8_t mute_mask, uint8_t priority) {
    (void)bank; (void)sample; (void)mute_mask; (void)priority;
}

#endif
