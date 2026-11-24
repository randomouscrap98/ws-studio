.module script_c35_switch

.include "vm.i"
.include "data/game_globals.i"

.area _CODE_255

; C35 orientation-switch test.  The scene starts horizontal.  After 60 idle
; ticks it switches to vertical, waits another 60 ticks and switches back to
; horizontal.  The frame checks sample one tick inside each phase; the world
; state must be identical before and after the switches.
_script_c35_switch::
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


        VM_SET_ORIENTATION      .ORIENTATION_VERTICAL
        VM_SET_CONST_INT8       _c35_phase, 2

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


        VM_SET_ORIENTATION      .ORIENTATION_HORIZONTAL
        VM_SET_CONST_INT8       _c35_phase, 3

        VM_STOP
