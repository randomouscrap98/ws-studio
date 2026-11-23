.module script_c18_blank

.include "vm.i"
.include "data/game_globals.i"

.area _CODE_255

.LOCAL_ACTOR = -4

; C18 blank-border: a 20x18 logo background centred on the 224-px screen.
; The 13x10 dialogue box sits at (64, 32) and stays clear of the 32-px
; border on each side.  Eight lines are long enough to walk the text tile
; buffer from 0xCC through 0xFF, so tile 0xFF (the old blank tile) is loaded.
_script_c18_blank::
        VM_SET_CONST_INT8       _wsc_test_marker, 2
        VM_LOCK
        VM_RESERVE              4
        VM_SET_CONST            .LOCAL_ACTOR, 0
        VM_ACTOR_DEACTIVATE     .LOCAL_ACTOR

        VM_OVERLAY_SHOW         8, 4, .UI_COLOR_BLACK, 0
        VM_OVERLAY_CLEAR        0, 0, 13, 10, .UI_COLOR_WHITE, .UI_DRAW_FRAME
        VM_SWITCH_TEXT_LAYER    .TEXT_LAYER_WIN

        VM_LOAD_TEXT            0
        .asciz "\001\001ABCDEFGHIJK\012LMNOPQRSTUV\012WXYZabcdefg\012hijklmnopqr\012stuvwxyz012\0123456789 !?.\012,:;'-()+/=<\012>ABCDEFGHIJ"
        VM_DISPLAY_TEXT

        VM_OVERLAY_WAIT         .UI_MODAL, ^/(.UI_WAIT_WINDOW | .UI_WAIT_TEXT | .UI_WAIT_BTN_A)/

        VM_STOP
