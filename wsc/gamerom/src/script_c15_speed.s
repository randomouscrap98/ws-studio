.module script_c15_speed

.include "vm.i"
.include "data/game_globals.i"

.area _CODE_255

; C15 text-speed: same overlay and text as text-instant, but \001\003
; selects text speed index 2.  ui_time_masks[2] = 1, so ui_update() renders
; one character on game frames where (game_time & 1) == 0.
_script_c15_speed::
        VM_LOCK

        VM_OVERLAY_SHOW         1, 1, .UI_COLOR_BLACK, 0
        VM_OVERLAY_CLEAR        0, 0, 20, 4, .UI_COLOR_WHITE, .UI_DRAW_FRAME
        VM_OVERLAY_SET_SCROLL   1, 1, 18, 5, .UI_COLOR_WHITE
        VM_SWITCH_TEXT_LAYER    .TEXT_LAYER_WIN

        VM_LOAD_TEXT            0
        .asciz "\001\003Wow! Found\012GOLD COIN."
        VM_DISPLAY_TEXT

        VM_OVERLAY_WAIT         .UI_MODAL, ^/(.UI_WAIT_WINDOW | .UI_WAIT_TEXT | .UI_WAIT_BTN_A)/

        VM_STOP
