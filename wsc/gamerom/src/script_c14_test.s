.module script_c14_test

.include "vm.i"
.include "data/game_globals.i"

.area _CODE_255

; Test scene script for C14 (screen-2 overlay window).
;
; The player starts at (48, 80) px, so the town camera shows source (0, 16)
; px.  Actor 4 (the Duck) is moved to (96, 120) px; on screen that is
; (96, 104), under the window at rest, so actor rendering must hide it.
;
; Window path:
;   SHOW at (1, 0) fills the runtime window width (27x18 tiles) in black.
;   MOVE_TO (1, 18) instantly closes it at the bottom edge.
;   MOVE_TO (1, 9) at speed 1 (one pixel per game frame) moves it in.
;   CLEAR 27x6 with a frame paints the framed area and leaves the lower
;   three rows as the black SHOW fill visible at rest.
;   WAIT for the window to arrive.
.LOCAL_ACTOR = -4

_script_c14_test::
        VM_LOCK
        VM_RESERVE              4

        ; Actor Set Position: actor 4 (Duck) -> (96, 120) px
        VM_SET_CONST            .LOCAL_ACTOR, 4
        VM_SET_CONST            ^/(.LOCAL_ACTOR + 1)/, 3072
        VM_SET_CONST            ^/(.LOCAL_ACTOR + 2)/, 3840
        VM_ACTOR_SET_POS        .LOCAL_ACTOR
        VM_ACTOR_SET_DIR        .LOCAL_ACTOR, .DIR_DOWN
        VM_SET_CONST            ^/(.LOCAL_ACTOR + 1)/, 0
        VM_ACTOR_SET_ANIM_FRAME .LOCAL_ACTOR
        VM_ACTOR_SET_ANIM_TICK  .LOCAL_ACTOR, 255

        ; Overlay: clear the full window at x=1, then hide it.
        VM_OVERLAY_SHOW         1, 0, .UI_COLOR_BLACK, 0
        VM_OVERLAY_MOVE_TO      1, 18, .OVERLAY_SPEED_INSTANT

        ; Move in from the bottom edge at 1 pixel per frame.
        VM_OVERLAY_MOVE_TO      1, 9, 1

        ; Clear the visible area at rest and draw the frame.
        VM_OVERLAY_CLEAR        0, 0, 27, 6, .UI_COLOR_BLACK, .UI_DRAW_FRAME

        VM_OVERLAY_WAIT         .UI_NONMODAL, .UI_WAIT_WINDOW

        VM_STOP
