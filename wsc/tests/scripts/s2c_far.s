.module s2c_far

.include "vm.i"

.area _CODE_255

_s2c_far::
        VM_SET_CONST            6, 0x42
        VM_RET_FAR
