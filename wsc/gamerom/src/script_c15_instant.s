.module script_c15_instant

.include "vm.i"
.include "data/game_globals.i"

.area _CODE_255

; C15 text-instant / text-wait.
;
; Screen-2 overlay at (1, 1) = pixel (8, 8), covering the runtime screen.
; The 20x4 framed box starts at window cell (0, 0); text is printed from
; cell (1, 1), i.e. pixel (16, 16) relative to the screen.
;
; \001\001 selects text speed index 0 (instant).  \012 is the explicit
; newline emitted by the GB Studio compiler.
_script_c15_instant::
        VM_LOCK

        VM_OVERLAY_SHOW         1, 1, .UI_COLOR_BLACK, 0
        VM_OVERLAY_CLEAR        0, 0, 20, 4, .UI_COLOR_WHITE, .UI_DRAW_FRAME
        VM_OVERLAY_SET_SCROLL   1, 1, 18, 5, .UI_COLOR_WHITE
        VM_SWITCH_TEXT_LAYER    .TEXT_LAYER_WIN

        VM_LOAD_TEXT            0
        .asciz "\001\001Wow! Found\012GOLD COIN."
        VM_DISPLAY_TEXT

        ; Modal: wait for the text to finish and for A.  The non-A run stays
        ; here, so VAR_QUEST10 remains 0; the A run falls through to set it.
        VM_OVERLAY_WAIT         .UI_MODAL, ^/(.UI_WAIT_WINDOW | .UI_WAIT_TEXT | .UI_WAIT_BTN_A)/

        VM_SET_CONST            VAR_QUEST10, 1
        VM_STOP
