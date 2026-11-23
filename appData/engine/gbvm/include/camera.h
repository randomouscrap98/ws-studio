#ifndef CAMERA_H
#define CAMERA_H

#include <gbdk/platform.h>

#ifdef __ia16__
/* The visible size comes from the WSC HAL so a vertical mode can change it
 * at runtime. */
#include "hal.h"
#define SCREEN_WIDTH      (hal_screen_w_px)
#define SCREEN_HEIGHT     (hal_screen_h_px)
#define SCREEN_WIDTH_HALF ((hal_screen_w_px) >> 1)
#define SCREEN_HEIGHT_HALF ((hal_screen_h_px) >> 1)
#else
#define SCREEN_WIDTH 160
#define SCREEN_HEIGHT 144
#define SCREEN_WIDTH_HALF 80
#define SCREEN_HEIGHT_HALF 72
#endif

#define CAMERA_UNLOCKED 0x00
#define CAMERA_LOCK_X_FLAG 0x01
#define CAMERA_LOCK_Y_FLAG 0x02
#define CAMERA_LOCK_X_MIN_FLAG 0x04
#define CAMERA_LOCK_X_MAX_FLAG 0x08
#define CAMERA_LOCK_Y_MIN_FLAG 0x10
#define CAMERA_LOCK_Y_MAX_FLAG 0x20
#define CAMERA_LOCK_FLAG (CAMERA_LOCK_X_FLAG | CAMERA_LOCK_Y_FLAG)

extern UINT16 camera_x;
extern UINT16 camera_y;
extern UINT16 camera_clamp_x;
extern UINT16 camera_clamp_y;
extern BYTE camera_offset_x;
extern BYTE camera_offset_y;
extern BYTE camera_deadzone_x;
extern BYTE camera_deadzone_y;
extern UBYTE camera_settings;

void camera_init(void) BANKED;

inline void camera_reset(void) {
    camera_deadzone_x = camera_deadzone_y = 0;
}

void camera_update(void) BANKED;

#endif