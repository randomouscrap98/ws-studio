.module s2c_main

.include "vm.i"

.area _CODE_255

_s2c_main::
        VM_LOCK

        ; constant
        VM_SET_CONST            0, 10

        ; RPN arithmetic: 7 + 5 -> variable 1
        VM_RPN
            .R_INT16    7
            .R_INT16    5
            .R_OPERATOR .ADD
            .R_REF_SET  1
            .R_STOP

        ; conditional jump
        VM_IF_CONST             .NE, 1, 0, 1$, 0
        VM_SET_CONST            2, 111
        VM_JUMP                 2$
1$:
        VM_SET_CONST            2, 222
2$:

        ; loop: increment variable 4 three times
        VM_SET_CONST            3, 3
        VM_SET_CONST            4, 0
3$:
        VM_LOOP                 3, 4$, 0
        VM_JUMP                 5$
4$:
        VM_RPN
            .R_REF      4
            .R_INT8     1
            .R_OPERATOR .ADD
            .R_REF_SET  4
            .R_STOP
        VM_JUMP                 3$
5$:

        ; far call into a different bank, then continue here
        VM_CALL_FAR             ___bank_s2c_far, _s2c_far
        VM_SET_CONST            5, 1

        ; C RAM symbols are reached through vm_ram_syms[]
        VM_SET_CONST_INT8       _s2c_ram_i8, 0x5A
        VM_SET_CONST_INT16      _s2c_ram_i16, 0x1234
        VM_GET_INT8             7, _s2c_ram_i8
        VM_GET_INT16            8, _s2c_ram_i16

        ; direct RPN memory refs, including an offset RAM operand
        VM_RPN
            .R_REF_MEM          .MEM_U8, _s2c_ram_bytes
            .R_REF_SET          9
            .R_STOP
        VM_RPN
            .R_REF_MEM          .MEM_U8, ^/(_s2c_ram_bytes + 1)/
            .R_REF_SET          10
            .R_STOP

        ; far C data through vm_far_data[], reading a word at an odd offset
        VM_GET_FAR             11, .GET_WORD, ___bank_s2c_far_data, ^/(_s2c_far_data + 1)/
        VM_STOP
