/* GBVM core on the WonderSwan Color: two script banks in ROM, run by the
 * portable dispatcher, with results visible in script_memory and IRAM. */

#include <stdint.h>

#include "vm.h"
#include "vm_bytecode.h"

/* RPN helper macros for the little-endian words embedded in the stream. */
#define R_INT8(v) (UBYTE)(VM_OP_INT8), (UBYTE)(v)
#define R_INT16(v) (UBYTE)(VM_OP_INT16), (UBYTE)(v), (UBYTE)((UWORD)(v) >> 8)
#define R_REF(i) (UBYTE)(VM_OP_REF), (UBYTE)(i), (UBYTE)((UWORD)(i) >> 8)
#define R_REF_SET(i) (UBYTE)(VM_OP_REF_SET), (UBYTE)(i), (UBYTE)((UWORD)(i) >> 8)
#define R_REF_MEM(t, a) \
    (UBYTE)(VM_OP_REF_MEM), (UBYTE)(t), (UBYTE)(a), (UBYTE)((UWORD)(a) >> 8)
#define R_REF_MEM_SET(t, a) \
    (UBYTE)(VM_OP_REF_MEM_SET), (UBYTE)(t), (UBYTE)(a), (UBYTE)((UWORD)(a) >> 8)
#define R_OP(o) (UBYTE)(o)
#define R_STOP (UBYTE)VM_OP_STOP

/* Switch table entries: both the test value and the target are little-endian
 * words read from the byte stream. */
#define R_CASE(v, l) \
    (UBYTE)(v), (UBYTE)((UWORD)(v) >> 8), (UBYTE)(l), (UBYTE)((UWORD)(l) >> 8)

/* Label offsets inside vmrom_bank0[]. Keep these in sync with the array. */
#define L_IF_TAKEN       0x3B
#define L_IF_JOIN        0x40
#define L_IFCONST_TAKEN  0x54
#define L_IFCONST_END    0x59
#define L_SUB            0x64
#define L_CALL_END       0x6B
#define L_LOOP_TOP       0x79
#define L_LOOP_BODY      0x82
#define L_LOOP_END       0x90
#define L_CASE1          0xAA
#define L_CASE2          0xB2
#define L_SWITCH_END     0xB7
#define L_THREAD1        0xD3
#define L_THREAD2        0xDF
#define L_THREADS_END    0xEB

const uint8_t __far vmrom_bank0[] = {
    /* RPN arithmetic: [0] = 7 + 5, [1] = 20 - 3, [2] = 6 * 7 */
    VM_RPN, R_INT16(7), R_INT16(5), R_OP(VM_OP_ADD), R_REF_SET(0), R_STOP,
    VM_RPN, R_INT16(20), R_INT16(3), R_OP(VM_OP_SUB), R_REF_SET(1), R_STOP,
    VM_RPN, R_INT16(6), R_INT16(7), R_OP(VM_OP_MUL), R_REF_SET(2), R_STOP,

    /* if/jump: taken branch writes 222 into [3] */
    VM_PUSH_CONST(3), VM_PUSH_CONST(3),
    VM_IF(VM_OP_EQ, -2, -1, L_IF_TAKEN, 2),
    VM_SET_CONST(3, 111),
    VM_JUMP(L_IF_JOIN),
    VM_SET_CONST(3, 222),              /* L_IF_TAKEN */

    /* if_const not taken: falls through and writes 111 into [4] */
    VM_PUSH_CONST(5),
    VM_IF_CONST(VM_OP_EQ, -1, 6, L_IFCONST_TAKEN, 1),
    VM_SET_CONST(4, 111),
    VM_JUMP(L_IFCONST_END),
    VM_SET_CONST(4, 222),              /* L_IFCONST_TAKEN */

    /* call/ret: subroutine writes 2 into [5], caller writes 1 into [6] */
    VM_CALL(L_SUB),
    VM_SET_CONST(6, 1),
    VM_JUMP(L_CALL_END),
    VM_SET_CONST(5, 2),                /* L_SUB */
    VM_RET,                            /* L_CALL_END follows */

    /* call_far/ret_far into bank 1; bank 1 writes [7] = 0x41 */
    VM_CALL_FAR(1, 0),
    VM_SET_CONST(8, 1),

    /* loop: run the body three times, counting into [10] */
    VM_SET_CONST(9, 3),
    VM_LOOP(9, L_LOOP_BODY, 0),        /* L_LOOP_TOP */
    VM_JUMP(L_LOOP_END),
    VM_RPN, R_REF(10), R_INT8(1), R_OP(VM_OP_ADD), R_REF_SET(10), R_STOP,
    VM_JUMP(L_LOOP_TOP),
    /* L_LOOP_END */

    /* switch: selector 2 matches the second case, writing 2 into [12] */
    VM_SET_CONST(11, 2),
    VM_SWITCH(11, 2, 0),
    R_CASE(1, L_CASE1),
    R_CASE(2, L_CASE2),
    VM_SET_CONST(12, 111),             /* default */
    VM_JUMP(L_SWITCH_END),
    VM_SET_CONST(12, 1),               /* L_CASE1 */
    VM_JUMP(L_SWITCH_END),
    VM_SET_CONST(12, 2),               /* L_CASE2 */
    /* L_SWITCH_END */

    /* two threads with join; handles go into [13] and [14] */
    VM_BEGINTHREAD(0, L_THREAD1, 13, 0),
    VM_BEGINTHREAD(0, L_THREAD2, 14, 0),
    VM_JOIN(13),
    VM_JOIN(14),
    VM_SET_CONST(15, 1),
    VM_JUMP(L_THREADS_END),
    VM_SET_CONST(16, 0x11), VM_IDLE, VM_SET_CONST(17, 0x12), VM_STOP,
    VM_SET_CONST(18, 0x21), VM_IDLE, VM_SET_CONST(19, 0x22), VM_STOP,
    /* L_THREADS_END */

    /* invoke wait_frames(3), then write [21] = 1 */
    VM_SET_CONST(20, 3),
    VM_INVOKE(0, 0, 0, 20),
    VM_SET_CONST(21, 1),

    /* RPN REF_MEM: write/read a byte at IRAM 0x1000 and a word at 0x1002. */
    VM_RPN, R_INT8(0xA5), R_REF_MEM_SET(VM_OP_MEM_U8, 0x1000), R_STOP,
    VM_RPN, R_REF_MEM(VM_OP_MEM_U8, 0x1000), R_REF_SET(22), R_STOP,
    VM_RPN, R_INT16(0xBEEF), R_REF_MEM_SET(VM_OP_MEM_I16, 0x1002), R_STOP,
    VM_RPN, R_REF_MEM(VM_OP_MEM_I16, 0x1002), R_REF_SET(23), R_STOP,

    /* VM_GET_FAR from bank 1: byte at offset 7, word at offset 8. */
    VM_GET_FAR(24, 0, 1, 7),
    VM_GET_FAR(25, 1, 1, 8),

    VM_STOP,
};

const uint8_t __far vmrom_bank1[] = {
    VM_SET_CONST(7, 0x41),
    VM_RET_FAR,
    /* Data read by the VM_GET_FAR instructions above. */
    0x9C, 0x34, 0x12,
};

/* Fixed IRAM addresses used by the REF_MEM instructions above. */
volatile uint8_t __attribute__((section(".iram_1000"))) vmrom_mem_byte;
volatile uint16_t __attribute__((section(".iram_1002"))) vmrom_mem_word;

/* Named RAM results checked by wsrun. */
volatile UWORD vmrom_done;
volatile UWORD vmrom_frames;
volatile UWORD vmrom_named_byte;
volatile UWORD vmrom_named_word;

/* Returning so the compiler restores %ds after the VM's far reads. */
__attribute__((noinline)) static void vmrom_tick(void) {
    UBYTE status;
    if (vmrom_done) return;
    wait_vbl_done();
    vmrom_frames++;
    status = script_runner_update();
    if (status == RUNNER_DONE) {
        vmrom_named_byte = vmrom_mem_byte;
        vmrom_named_word = vmrom_mem_word;
        vmrom_done = 1;
    }
}

void main(void) {
    script_runner_init(1);
    script_execute(0, vmrom_bank0, NULL, 0);
    while (1) vmrom_tick();
}
