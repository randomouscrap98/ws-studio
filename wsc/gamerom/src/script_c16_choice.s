.module script_c16_choice

.include "vm.i"
.include "data/game_globals.i"

.area _CODE_255

; C16 menu test.
;
; The overlay is at (1, 1) = pixel (8, 8) and the 20x5 framed box starts at
; window cell (0, 0).  Text starts at cell (1, 1), so the prompt is row 1 and
; the three labels are rows 2, 3 and 4.
;
; \001\001 is text speed index 0 (instant); \012 is the explicit newline the
; GB Studio compiler emits.  VAR_QUEST10 is set to 7 first, so a test can
; tell "cancelled to 0" from "menu never returned".
_script_c16_choice::
        VM_LOCK

        VM_OVERLAY_SHOW         1, 1, .UI_COLOR_BLACK, 0
        VM_OVERLAY_CLEAR        0, 0, 20, 5, .UI_COLOR_WHITE, .UI_DRAW_FRAME
        VM_OVERLAY_SET_SCROLL   1, 1, 18, 5, .UI_COLOR_WHITE
        VM_SWITCH_TEXT_LAYER    .TEXT_LAYER_WIN

        VM_SET_CONST            VAR_QUEST10, 7

        VM_LOAD_TEXT            0
        .asciz "\001\001Pick one:\0121 - One\0122 - Two\0123 - Three"
        VM_DISPLAY_TEXT
        VM_OVERLAY_WAIT         .UI_MODAL, ^/(.UI_WAIT_WINDOW | .UI_WAIT_TEXT)/

        ; Vertical 3-item menu.  Down from item 1 goes to item 2 (whose result
        ; value is 2), and the last item or B returns 0.
        VM_CHOICE               VAR_QUEST10, ^/(.UI_MENU_LAST_0 | .UI_MENU_CANCEL_B)/, 3
            .MENUITEM           1, 2, 0, 0, 0, 2
            .MENUITEM           1, 3, 0, 0, 1, 3
            .MENUITEM           1, 4, 0, 0, 2, 0

        ; Close the overlay, then stop.  The frame after this shows the town
        ; scene with the menu window hidden.
        VM_OVERLAY_MOVE_TO      0, 18, .OVERLAY_SPEED_INSTANT
        VM_OVERLAY_WAIT         .UI_MODAL, ^/(.UI_WAIT_WINDOW | .UI_WAIT_TEXT)/
        VM_STOP
