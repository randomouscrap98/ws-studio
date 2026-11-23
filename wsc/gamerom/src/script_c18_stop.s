.module script_c18_stop

.include "vm.i"
.include "data/game_globals.i"

.area _CODE_255

.LOCAL_ACTOR = -4

; C18 tiles-big: hide the player so the frame is background-only, then stop.
_script_c18_stop::
        VM_SET_CONST_INT8       _wsc_test_marker, 2
        VM_LOCK
        VM_RESERVE              4
        VM_SET_CONST            .LOCAL_ACTOR, 0
        VM_ACTOR_DEACTIVATE     .LOCAL_ACTOR
        VM_STOP
