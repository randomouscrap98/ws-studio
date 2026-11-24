; Deliberately broken input for `make -C wsc s2c-equiv`.
; Both s2c implementations must reject the unknown macro.
.module s2c_error_unknown_macro

.include "vm.i"

.area _CODE_255

_s2c_error_unknown_macro::
        VM_NOT_A_REAL_MACRO 1
