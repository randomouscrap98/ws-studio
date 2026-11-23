.module script_c15_var

.include "vm.i"
.include "data/game_globals.i"

.area _CODE_255

; C15 text-var: two variables, one negative and one multi-digit.  The
; compiler emits %d placeholders in the .asciz string and the variable
; indices as .dw words before it.
_script_c15_var::
        VM_LOCK

        VM_SET_CONST            VAR_QUEST10, -42
        VM_SET_CONST            VAR_TURNIP_COUNTER, 1234

        VM_OVERLAY_SHOW         1, 1, .UI_COLOR_BLACK, 0
        VM_OVERLAY_CLEAR        0, 0, 20, 4, .UI_COLOR_WHITE, .UI_DRAW_FRAME
        VM_OVERLAY_SET_SCROLL   1, 1, 18, 5, .UI_COLOR_WHITE
        VM_SWITCH_TEXT_LAYER    .TEXT_LAYER_WIN

        VM_LOAD_TEXT            2
        .dw VAR_QUEST10, VAR_TURNIP_COUNTER
        .asciz "\001\001Var: %d and %d."
        VM_DISPLAY_TEXT

        VM_OVERLAY_WAIT         .UI_MODAL, ^/(.UI_WAIT_WINDOW | .UI_WAIT_TEXT | .UI_WAIT_BTN_A)/

        VM_STOP
