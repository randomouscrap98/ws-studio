.module script_c13_test

.include "vm.i"
.include "data/game_globals.i"

.area _CODE_255

; Test scene script for C13.  All coordinates are subpixels (pixels << 5),
; matching VM_ACTOR_* and VM_CAMERA_* operands.
;
; Actor 4 is the Duck from scene_sample_town_actors[] (actors[4], i.e. the
; fourth scene actor).  The room's initial camera shows it.
;
; The script's constants:
;   ACTOR_FROM_X = 96 px  = 3072
;   ACTOR_FROM_Y = 80 px  = 2560
;   ACTOR_TO_X   = 128 px = 4096
;   ACTOR_TO_Y   = 80 px  = 2560
;   ACTOR_FRAME  = 1
;   CAMERA_X     = 144 px = 4608
;   CAMERA_Y     = 88 px  = 2816
.LOCAL_ACTOR = -4

_script_c13_test::
        VM_SET_CONST_INT8       _wsc_test_marker, 2
        VM_LOCK
        VM_RESERVE              4

        ; Actor Set Position: actor 4 -> (96, 80) px
        VM_SET_CONST            .LOCAL_ACTOR, 4
        VM_SET_CONST            ^/(.LOCAL_ACTOR + 1)/, 3072
        VM_SET_CONST            ^/(.LOCAL_ACTOR + 2)/, 2560
        VM_ACTOR_SET_POS        .LOCAL_ACTOR

        ; Actor Move To: (128, 80) px, no collision checks
        VM_SET_CONST            ^/(.LOCAL_ACTOR + 1)/, 4096
        VM_SET_CONST            ^/(.LOCAL_ACTOR + 2)/, 2560
        VM_SET_CONST            ^/(.LOCAL_ACTOR + 3)/, 0
        VM_ACTOR_MOVE_TO        .LOCAL_ACTOR

        ; Face left and select animation frame 1 of the two-frame duck walk.
        ; 255 pauses animation so the frame stays fixed for the frame check.
        VM_ACTOR_SET_DIR        .LOCAL_ACTOR, .DIR_LEFT
        VM_SET_CONST            ^/(.LOCAL_ACTOR + 1)/, 1
        VM_ACTOR_SET_ANIM_FRAME .LOCAL_ACTOR
        VM_ACTOR_SET_ANIM_TICK  .LOCAL_ACTOR, 255

        ; Deactivate and immediately reactivate actor 1 (the cat).
        VM_SET_CONST            .LOCAL_ACTOR, 1
        VM_ACTOR_DEACTIVATE     .LOCAL_ACTOR
        VM_ACTOR_ACTIVATE       .LOCAL_ACTOR

        ; Switch drawing from the boot default 8x16 to 8x8.
        VM_SET_SPRITE_MODE      .MODE_8X8

        ; Move the camera to (144, 88) px = subpixels (4608, 2816).
        ; 128 subpixels/frame; AFTER_LOCK=0 leaves the camera unlocked.
        VM_SET_CONST            .LOCAL_ACTOR, 4608
        VM_SET_CONST            ^/(.LOCAL_ACTOR + 1)/, 2816
        VM_CAMERA_MOVE_TO       .LOCAL_ACTOR, 128, 0

        VM_STOP
