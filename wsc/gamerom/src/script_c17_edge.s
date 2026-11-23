.module script_c17_edge

.include "vm.i"
.include "data/game_globals.i"

.area _CODE_255

; C17 sprite-edge test script.  Coordinates are subpixels (pixels << 5).
;
; The camera is moved to source (32, 16) first.  Then the Cat (actor 1,
; scene_sample_town_actors[0]) is placed with its 16-px sprite half off the
; left edge, and the Duck (actor 4, scene_sample_town_actors[3]) is placed
; with its origin 40 px past the right edge.  The HAL must drop the Duck's
; entries and keep the Cat's partly visible left entry.
;
;   CAT_X    = 20 px  = 640   -> screen x -12 (tiles at -4 and 4)
;   CAT_Y    = 48 px  = 1536  -> screen y 32
;   DUCK_X   = 296 px = 9472  -> screen x 264
;   DUCK_Y   = 80 px  = 2560  -> screen y 64
;   CAMERA_X = 144 px = 4608
;   CAMERA_Y = 88 px  = 2816
.LOCAL_ACTOR = -4

_script_c17_edge::
        VM_SET_CONST_INT8       _wsc_test_marker, 2
        VM_LOCK
        VM_RESERVE              4

        ; Move the camera to (144, 88) px = subpixels (4608, 2816).
        ; 128 subpixels/frame; AFTER_LOCK=0 leaves the camera unlocked.
        VM_SET_CONST            .LOCAL_ACTOR, 4608
        VM_SET_CONST            ^/(.LOCAL_ACTOR + 1)/, 2816
        VM_CAMERA_MOVE_TO       .LOCAL_ACTOR, 128, 0

        ; Cat: (20, 48) px, facing down, frame 0, animation paused.
        VM_SET_CONST            .LOCAL_ACTOR, 1
        VM_SET_CONST            ^/(.LOCAL_ACTOR + 1)/, 640
        VM_SET_CONST            ^/(.LOCAL_ACTOR + 2)/, 1536
        VM_ACTOR_SET_POS        .LOCAL_ACTOR
        VM_ACTOR_SET_DIR        .LOCAL_ACTOR, .DIR_DOWN
        VM_SET_CONST            ^/(.LOCAL_ACTOR + 1)/, 0
        VM_ACTOR_SET_ANIM_FRAME .LOCAL_ACTOR
        VM_ACTOR_SET_ANIM_TICK  .LOCAL_ACTOR, 255

        ; Duck: (296, 80) px, facing down, frame 0, animation paused.
        VM_SET_CONST            .LOCAL_ACTOR, 4
        VM_SET_CONST            ^/(.LOCAL_ACTOR + 1)/, 9472
        VM_SET_CONST            ^/(.LOCAL_ACTOR + 2)/, 2560
        VM_ACTOR_SET_POS        .LOCAL_ACTOR
        VM_ACTOR_SET_DIR        .LOCAL_ACTOR, .DIR_DOWN
        VM_SET_CONST            ^/(.LOCAL_ACTOR + 1)/, 0
        VM_ACTOR_SET_ANIM_FRAME .LOCAL_ACTOR
        VM_ACTOR_SET_ANIM_TICK  .LOCAL_ACTOR, 255

        ; Switch drawing from the boot default 8x16 to 8x8.
        VM_SET_SPRITE_MODE      .MODE_8X8

        VM_STOP
