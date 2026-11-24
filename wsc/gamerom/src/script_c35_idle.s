.module script_c35_idle

.include "vm.i"
.include "data/game_globals.i"

.area _CODE_255

; C35 switch control: the same town scene and tick sequence as
; script_c35_switch, but without either orientation call.  The switch test
; compares the world state at the same tick in both runs.
_script_c35_idle::
        VM_SET_CONST_INT8       _wsc_test_marker, 2
        VM_SET_CONST_INT8       _c35_phase, 1

        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_IDLE
        VM_SET_CONST_INT8       _c35_phase, 3

        VM_STOP
