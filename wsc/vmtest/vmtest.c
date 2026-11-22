/* Host tests for the portable GBVM core. */

#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "vm.h"
#include "vm_bytecode.h"

#define HOST_BANKS 4
#define MAX_CODE 2048
#define MAX_LABELS 64
#define MAX_FIXUPS 64
#define MAX_UPDATES 1000

static const UBYTE *host_banks[HOST_BANKS];

const UBYTE *vm_bank_base(UBYTE bank) {
    if (bank >= HOST_BANKS || host_banks[bank] == NULL) {
        fprintf(stderr, "vmtest: bank %u is not registered\n", bank);
        abort();
    }
    return host_banks[bank];
}

extern UBYTE vm_last_unimplemented_opcode;

static int checks_passed;
static int checks_failed;

static void check_eq(const char *name, long got, long want) {
    if (got == want) {
        printf("PASS %s\n", name);
        checks_passed++;
    } else {
        printf("FAIL %s: got %ld, want %ld\n", name, got, want);
        checks_failed++;
    }
}

static void check_true(const char *name, int condition, const char *reason) {
    if (condition) {
        printf("PASS %s\n", name);
        checks_passed++;
    } else {
        printf("FAIL %s: %s\n", name, reason);
        checks_failed++;
    }
}

typedef struct code {
    UBYTE bytes[MAX_CODE];
    int len;
    int labels[MAX_LABELS];
    int nlabels;
    struct {
        int pos;
        int label;
        int little;
    } fixups[MAX_FIXUPS];
    int nfix;
} Code;

static void code_init(Code *c) {
    memset(c, 0, sizeof(*c));
    for (int i = 0; i < MAX_LABELS; i++) c->labels[i] = -1;
}

static int label_new(Code *c) {
    if (c->nlabels >= MAX_LABELS) {
        fprintf(stderr, "vmtest: too many labels\n");
        abort();
    }
    return c->nlabels++;
}

static void label_place(Code *c, int label) {
    c->labels[label] = c->len;
}

static void label_place_at(Code *c, int label, int offset) {
    c->labels[label] = offset;
}

static void emit_bytes(Code *c, const UBYTE *bytes, int count) {
    if (c->len + count > MAX_CODE) {
        fprintf(stderr, "vmtest: bytecode overflow\n");
        abort();
    }
    memcpy(c->bytes + c->len, bytes, (size_t)count);
    c->len += count;
}

static void emit_byte(Code *c, UBYTE byte) {
    emit_bytes(c, &byte, 1);
}

static void add_fixup(Code *c, int pos, int label, int little) {
    if (c->nfix >= MAX_FIXUPS) {
        fprintf(stderr, "vmtest: too many fixups\n");
        abort();
    }
    c->fixups[c->nfix].pos = pos;
    c->fixups[c->nfix].label = label;
    c->fixups[c->nfix].little = little;
    c->nfix++;
}

static void emit_target(Code *c, int label, const UBYTE *bytes, int count) {
    int start = c->len;
    int pos = -1;
    emit_bytes(c, bytes, count);
    for (int i = 0; i + 1 < count; i++) {
        if (bytes[i] == 0xAA && bytes[i + 1] == 0xBB) pos = start + i;
    }
    if (pos < 0) {
        fprintf(stderr, "vmtest: target placeholder not found\n");
        abort();
    }
    add_fixup(c, pos, label, 0);
}

static void code_finalize(Code *c) {
    for (int i = 0; i < c->nfix; i++) {
        int target = c->labels[c->fixups[i].label];
        if (target < 0) {
            fprintf(stderr, "vmtest: unplaced label %d (code length %d)\n",
                    c->fixups[i].label, c->len);
            abort();
        }
        if (c->fixups[i].little) {
            c->bytes[c->fixups[i].pos] = (UBYTE)target;
            c->bytes[c->fixups[i].pos + 1] = (UBYTE)(target >> 8);
        } else {
            c->bytes[c->fixups[i].pos] = (UBYTE)(target >> 8);
            c->bytes[c->fixups[i].pos + 1] = (UBYTE)target;
        }
    }
}

/* Instruction emitters built from the generated vm.i macros. */
static void emit_push_const(Code *c, UWORD v) { const UBYTE b[] = { VM_PUSH_CONST(v) }; emit_bytes(c, b, (int)sizeof b); }
static void emit_pop(Code *c, UBYTE n) { const UBYTE b[] = { VM_POP(n) }; emit_bytes(c, b, (int)sizeof b); }
static void emit_reserve(Code *c, INT8 n) { const UBYTE b[] = { VM_RESERVE(n) }; emit_bytes(c, b, (int)sizeof b); }
static void emit_set(Code *c, INT16 a, INT16 b) { const UBYTE x[] = { VM_SET(a, b) }; emit_bytes(c, x, (int)sizeof x); }
static void emit_set_const(Code *c, INT16 idx, UWORD v) { const UBYTE b[] = { VM_SET_CONST(idx, v) }; emit_bytes(c, b, (int)sizeof b); }
static void emit_push_value(Code *c, INT16 idx) { const UBYTE b[] = { VM_PUSH_VALUE(idx) }; emit_bytes(c, b, (int)sizeof b); }
static void emit_push_value_ind(Code *c, INT16 idx) { const UBYTE b[] = { VM_PUSH_VALUE_IND(idx) }; emit_bytes(c, b, (int)sizeof b); }
static void emit_set_indirect(Code *c, INT16 a, INT16 b) { const UBYTE x[] = { VM_SET_INDIRECT(a, b) }; emit_bytes(c, x, (int)sizeof x); }
static void emit_get_indirect(Code *c, INT16 a, INT16 b) { const UBYTE x[] = { VM_GET_INDIRECT(a, b) }; emit_bytes(c, x, (int)sizeof x); }
static void emit_stop(Code *c) { const UBYTE b[] = { VM_STOP }; emit_bytes(c, b, (int)sizeof b); }
static void emit_idle(Code *c) { const UBYTE b[] = { VM_IDLE }; emit_bytes(c, b, (int)sizeof b); }
static void emit_ret(Code *c) { const UBYTE b[] = { VM_RET }; emit_bytes(c, b, (int)sizeof b); }
static void emit_ret_far(Code *c) { const UBYTE b[] = { VM_RET_FAR }; emit_bytes(c, b, (int)sizeof b); }
static void emit_rpn(Code *c) { const UBYTE b[] = { VM_RPN }; emit_bytes(c, b, (int)sizeof b); }
static void emit_switch(Code *c, INT16 idx, UBYTE size, UBYTE n) { const UBYTE b[] = { VM_SWITCH(idx, size, n) }; emit_bytes(c, b, (int)sizeof b); }
static void emit_memcpy(Code *c, INT16 dest, INT16 src, INT16 count) { const UBYTE b[] = { VM_MEMCPY(dest, src, count) }; emit_bytes(c, b, (int)sizeof b); }
static void emit_memset(Code *c, INT16 dest, INT16 value, INT16 count) { const UBYTE b[] = { VM_MEMSET(dest, value, count) }; emit_bytes(c, b, (int)sizeof b); }
static void emit_init_rng(Code *c, INT16 idx) { const UBYTE b[] = { VM_INIT_RNG(idx) }; emit_bytes(c, b, (int)sizeof b); }
static void emit_rand(Code *c, INT16 idx, UWORD min, UWORD limit) { const UBYTE b[] = { VM_RAND(idx, min, limit) }; emit_bytes(c, b, (int)sizeof b); }
static void emit_join(Code *c, INT16 idx) { const UBYTE b[] = { VM_JOIN(idx) }; emit_bytes(c, b, (int)sizeof b); }
static void emit_terminate(Code *c, INT16 idx) { const UBYTE b[] = { VM_TERMINATE(idx) }; emit_bytes(c, b, (int)sizeof b); }
static void emit_invoke(Code *c, UBYTE bank, UWORD fn, UBYTE nparams, INT16 idx) { const UBYTE b[] = { VM_INVOKE(bank, fn, nparams, idx) }; emit_bytes(c, b, (int)sizeof b); }

static void emit_jump(Code *c, int label) {
    const UBYTE b[] = { VM_JUMP(0xAABB) };
    emit_target(c, label, b, (int)sizeof b);
}
static void emit_call(Code *c, int label) {
    const UBYTE b[] = { VM_CALL(0xAABB) };
    emit_target(c, label, b, (int)sizeof b);
}
static void emit_call_far(Code *c, UBYTE bank, int label) {
    const UBYTE b[] = { VM_CALL_FAR(bank, 0xAABB) };
    emit_target(c, label, b, (int)sizeof b);
}
static void emit_if(Code *c, UBYTE cond, INT16 a, INT16 b, int label, UBYTE n) {
    const UBYTE x[] = { VM_IF(cond, a, b, 0xAABB, n) };
    emit_target(c, label, x, (int)sizeof x);
}
static void emit_if_const(Code *c, UBYTE cond, INT16 a, INT16 b, int label, UBYTE n) {
    const UBYTE x[] = { VM_IF_CONST(cond, a, b, 0xAABB, n) };
    emit_target(c, label, x, (int)sizeof x);
}
static void emit_loop(Code *c, INT16 idx, int label, UBYTE n) {
    const UBYTE b[] = { VM_LOOP(idx, 0xAABB, n) };
    emit_target(c, label, b, (int)sizeof b);
}
static void emit_beginthread(Code *c, UBYTE bank, int label, INT16 hthread, UBYTE nargs) {
    const UBYTE b[] = { VM_BEGINTHREAD(bank, 0xAABB, hthread, nargs) };
    emit_target(c, label, b, (int)sizeof b);
}

static void emit_case(Code *c, INT16 value, int label) {
    UBYTE v[2] = { (UBYTE)value, (UBYTE)((UWORD)value >> 8) };
    UBYTE t[2] = { 0xBB, 0xAA };
    emit_bytes(c, v, 2);
    int start = c->len;
    emit_bytes(c, t, 2);
    add_fixup(c, start, label, 1);
}

/* RPN sub-opcode emitters (little-endian .dw values, as in vm.i). */
static void rpn_i8(Code *c, INT8 v) { UBYTE b[2] = { (UBYTE)VM_OP_INT8, (UBYTE)v }; emit_bytes(c, b, 2); }
static void rpn_i16(Code *c, UWORD v) { UBYTE b[3] = { (UBYTE)VM_OP_INT16, (UBYTE)v, (UBYTE)(v >> 8) }; emit_bytes(c, b, 3); }
static void rpn_ref(Code *c, INT16 idx) { UBYTE b[3] = { (UBYTE)VM_OP_REF, (UBYTE)idx, (UBYTE)((UWORD)idx >> 8) }; emit_bytes(c, b, 3); }
static void rpn_ref_ind(Code *c, INT16 idx) { UBYTE b[3] = { (UBYTE)VM_OP_REF_IND, (UBYTE)idx, (UBYTE)((UWORD)idx >> 8) }; emit_bytes(c, b, 3); }
static void rpn_ref_set(Code *c, INT16 idx) { UBYTE b[3] = { (UBYTE)VM_OP_REF_SET, (UBYTE)idx, (UBYTE)((UWORD)idx >> 8) }; emit_bytes(c, b, 3); }
static void rpn_ref_set_ind(Code *c, INT16 idx) { UBYTE b[3] = { (UBYTE)VM_OP_REF_SET_IND, (UBYTE)idx, (UBYTE)((UWORD)idx >> 8) }; emit_bytes(c, b, 3); }
static void rpn_op(Code *c, UBYTE op) { emit_byte(c, op); }
static void rpn_stop(Code *c) { emit_byte(c, 0); }

static void rpn_bin(Code *c, INT16 a, UBYTE op, INT16 b, INT16 dest) {
    emit_rpn(c);
    rpn_i16(c, (UWORD)a);
    rpn_i16(c, (UWORD)b);
    rpn_op(c, op);
    rpn_ref_set(c, dest);
    rpn_stop(c);
}
static void rpn_unary(Code *c, INT16 a, UBYTE op, INT16 dest) {
    emit_rpn(c);
    rpn_i16(c, (UWORD)a);
    rpn_op(c, op);
    rpn_ref_set(c, dest);
    rpn_stop(c);
}

static UBYTE run_code(UBYTE bank, UBYTE *bytes, int *updates) {
    host_banks[bank] = bytes;
    script_runner_init(1);
    if (script_execute(bank, bytes, NULL, 0) == NULL) return 0xFF;
    int n = 0;
    UBYTE status;
    for (;;) {
        status = script_runner_update();
        n++;
        if (status == RUNNER_DONE || status == RUNNER_EXCEPTION) break;
        if (n >= MAX_UPDATES) return 0xFE;
    }
    if (updates) *updates = n;
    return status;
}

static void test_push_pop(void) {
    Code c;
    code_init(&c);
    emit_push_const(&c, 0x1234);
    emit_push_const(&c, 0x5678);
    emit_set(&c, 0, -1);
    emit_pop(&c, 1);
    emit_set(&c, 1, -1);
    emit_pop(&c, 1);
    emit_reserve(&c, 1);
    emit_set_const(&c, -1, 0x00AA);
    emit_set(&c, 2, -1);
    emit_reserve(&c, -1);
    emit_stop(&c);
    code_finalize(&c);

    UBYTE status = run_code(0, c.bytes, NULL);
    check_true("push_pop.run", status == RUNNER_DONE, "runner did not finish");
    check_eq("push_pop.pop_order", script_memory[0], 0x5678);
    check_eq("push_pop.remaining", script_memory[1], 0x1234);
    check_eq("push_pop.reserve", script_memory[2], 0x00AA);
}

static void test_indirect(void) {
    Code c;
    code_init(&c);
    emit_set_const(&c, 0, 3);
    emit_set_const(&c, 1, 0x55);
    emit_set_indirect(&c, 0, 1);
    emit_set_const(&c, 0, 4);
    emit_set_const(&c, 4, 0x66);
    emit_get_indirect(&c, 1, 0);
    emit_set_const(&c, 0, 3);
    emit_push_value_ind(&c, 0);
    emit_set(&c, 2, -1);
    emit_pop(&c, 1);
    emit_push_value(&c, 1);
    emit_set(&c, 5, -1);
    emit_pop(&c, 1);
    emit_stop(&c);
    code_finalize(&c);

    UBYTE status = run_code(0, c.bytes, NULL);
    check_true("indirect.run", status == RUNNER_DONE, "runner did not finish");
    check_eq("indirect.set", script_memory[3], 0x55);
    check_eq("indirect.get", script_memory[1], 0x66);
    check_eq("indirect.push_ind", script_memory[2], 0x55);
    check_eq("indirect.push_value", script_memory[5], 0x66);
}

static void test_rpn(void) {
    Code c;
    code_init(&c);
    rpn_bin(&c, 7, VM_OP_ADD, 5, 0);
    rpn_bin(&c, 20, VM_OP_SUB, 3, 1);
    rpn_bin(&c, 6, VM_OP_MUL, 7, 2);
    rpn_bin(&c, 100, VM_OP_DIV, 7, 3);
    rpn_bin(&c, 100, VM_OP_MOD, 7, 4);
    rpn_bin(&c, 3, VM_OP_LT, 5, 5);
    rpn_bin(&c, 5, VM_OP_LE, 5, 6);
    rpn_bin(&c, 5, VM_OP_GT, 9, 7);
    rpn_bin(&c, 5, VM_OP_NE, 5, 8);
    rpn_bin(&c, 3, VM_OP_EQ, 3, 9);
    rpn_bin(&c, 0, VM_OP_OR, 7, 10);
    rpn_bin(&c, 3, VM_OP_AND, 0, 11);
    rpn_unary(&c, 0, VM_OP_NOT, 12);
    rpn_bin(&c, 0xF0, VM_OP_B_AND, 0x3C, 13);
    rpn_bin(&c, 0xF0, VM_OP_B_OR, 0x3C, 14);
    rpn_bin(&c, 0xF0, VM_OP_B_XOR, 0x3C, 15);
    rpn_bin(&c, 1, VM_OP_SHL, 4, 16);
    rpn_bin(&c, 0x100, VM_OP_SHR, 3, 17);
    emit_set_const(&c, 18, 1234);
    emit_rpn(&c);
    rpn_ref(&c, 18);
    rpn_i8(&c, 2);
    rpn_op(&c, VM_OP_ADD);
    rpn_ref_set(&c, 19);
    rpn_stop(&c);
    emit_set_const(&c, 20, 18);
    emit_rpn(&c);
    rpn_ref_ind(&c, 20);
    rpn_ref_set(&c, 21);
    rpn_stop(&c);
    emit_set_const(&c, 22, 23);
    emit_rpn(&c);
    rpn_i8(&c, 9);
    rpn_ref_set_ind(&c, 22);
    rpn_stop(&c);
    emit_stop(&c);
    code_finalize(&c);

    UBYTE status = run_code(0, c.bytes, NULL);
    check_true("rpn.run", status == RUNNER_DONE, "runner did not finish");
    check_eq("rpn.add", script_memory[0], 12);
    check_eq("rpn.sub", script_memory[1], 17);
    check_eq("rpn.mul", script_memory[2], 42);
    check_eq("rpn.div", script_memory[3], 14);
    check_eq("rpn.mod", script_memory[4], 2);
    check_eq("rpn.lt", script_memory[5], 1);
    check_eq("rpn.le", script_memory[6], 1);
    check_eq("rpn.gt", script_memory[7], 0);
    check_eq("rpn.ne", script_memory[8], 0);
    check_eq("rpn.eq", script_memory[9], 1);
    check_eq("rpn.or", script_memory[10], 1);
    check_eq("rpn.and", script_memory[11], 0);
    check_eq("rpn.not", script_memory[12], 1);
    check_eq("rpn.b_and", script_memory[13], 0x30);
    check_eq("rpn.b_or", script_memory[14], 0xFC);
    check_eq("rpn.b_xor", script_memory[15], 0xCC);
    check_eq("rpn.shl", script_memory[16], 16);
    check_eq("rpn.shr", script_memory[17], 32);
    check_eq("rpn.ref", script_memory[19], 1236);
    check_eq("rpn.ref_ind", script_memory[21], 1234);
    check_eq("rpn.ref_set_ind", script_memory[23], 9);
}

static void test_branches(void) {
    Code c;
    code_init(&c);
    int if_taken = label_new(&c), if_join = label_new(&c);
    int ifconst_taken = label_new(&c), ifconst_join = label_new(&c);
    int if_not = label_new(&c), ifconst_not = label_new(&c);
    int jump_end = label_new(&c), sub = label_new(&c);

    emit_push_const(&c, 3);
    emit_push_const(&c, 3);
    emit_if(&c, VM_OP_EQ, -2, -1, if_taken, 2);
    emit_set_const(&c, 0, 111);
    emit_jump(&c, if_join);
    label_place(&c, if_taken);
    emit_set_const(&c, 0, 222);
    label_place(&c, if_join);

    emit_push_const(&c, 1);
    emit_push_const(&c, 2);
    emit_if(&c, VM_OP_EQ, -2, -1, if_not, 2);
    emit_set_const(&c, 1, 111);
    label_place(&c, if_not);

    emit_push_const(&c, 5);
    emit_if_const(&c, VM_OP_EQ, -1, 5, ifconst_taken, 1);
    emit_set_const(&c, 2, 111);
    emit_jump(&c, ifconst_join);
    label_place(&c, ifconst_taken);
    emit_set_const(&c, 2, 222);
    label_place(&c, ifconst_join);

    emit_push_const(&c, 5);
    emit_if_const(&c, VM_OP_EQ, -1, 6, ifconst_not, 1);
    emit_set_const(&c, 3, 111);
    label_place(&c, ifconst_not);

    emit_call(&c, sub);
    emit_set_const(&c, 4, 1);
    emit_jump(&c, jump_end);
    label_place(&c, sub);
    emit_set_const(&c, 5, 2);
    emit_ret(&c);
    emit_set_const(&c, 6, 999);
    label_place(&c, jump_end);
    emit_stop(&c);
    code_finalize(&c);

    UBYTE status = run_code(0, c.bytes, NULL);
    check_true("branches.run", status == RUNNER_DONE, "runner did not finish");
    check_eq("branches.if_taken", script_memory[0], 222);
    check_eq("branches.if_not_taken", script_memory[1], 111);
    check_eq("branches.if_const_taken", script_memory[2], 222);
    check_eq("branches.if_const_not_taken", script_memory[3], 111);
    check_eq("branches.call_ret", script_memory[4], 1);
    check_eq("branches.ret_body", script_memory[5], 2);
    check_eq("branches.jump", script_memory[6], 0);
}

static void test_call_far(void) {
    Code main_code, far_code;
    code_init(&main_code);
    code_init(&far_code);

    int far_entry = label_new(&main_code);
    label_place_at(&main_code, far_entry, 0);
    emit_call_far(&main_code, 1, far_entry);
    emit_set_const(&main_code, 0, 1);
    emit_stop(&main_code);

    emit_set_const(&far_code, 1, 2);
    emit_ret_far(&far_code);
    code_finalize(&main_code);
    code_finalize(&far_code);

    host_banks[1] = far_code.bytes;
    UBYTE status = run_code(0, main_code.bytes, NULL);
    check_true("call_far.run", status == RUNNER_DONE, "runner did not finish");
    check_eq("call_far.after_return", script_memory[0], 1);
    check_eq("call_far.remote_bank", script_memory[1], 2);
}

static void test_loop(void) {
    Code c;
    code_init(&c);
    int top = label_new(&c), body = label_new(&c);
    emit_set_const(&c, 0, 3);
    label_place(&c, top);
    emit_loop(&c, 0, body, 0);
    emit_stop(&c);
    label_place(&c, body);
    emit_rpn(&c);
    rpn_ref(&c, 1);
    rpn_i8(&c, 1);
    rpn_op(&c, VM_OP_ADD);
    rpn_ref_set(&c, 1);
    rpn_stop(&c);
    emit_jump(&c, top);
    code_finalize(&c);

    UBYTE status = run_code(0, c.bytes, NULL);
    check_true("loop.run", status == RUNNER_DONE, "runner did not finish");
    check_eq("loop.counter", script_memory[0], 0);
    check_eq("loop.body_runs", script_memory[1], 3);
}

static void test_switch(void) {
    Code c;
    code_init(&c);
    int one = label_new(&c), two = label_new(&c), def = label_new(&c), end = label_new(&c);
    emit_set_const(&c, 0, 2);
    emit_switch(&c, 0, 2, 0);
    emit_case(&c, 1, one);
    emit_case(&c, 2, two);
    label_place(&c, def);
    emit_set_const(&c, 1, 111);
    emit_jump(&c, end);
    label_place(&c, one);
    emit_set_const(&c, 1, 1);
    emit_jump(&c, end);
    label_place(&c, two);
    emit_set_const(&c, 1, 2);
    label_place(&c, end);
    emit_stop(&c);
    code_finalize(&c);

    UBYTE status = run_code(0, c.bytes, NULL);
    check_true("switch.match.run", status == RUNNER_DONE, "runner did not finish");
    check_eq("switch.match", script_memory[1], 2);

    Code d;
    code_init(&d);
    one = label_new(&d); two = label_new(&d); def = label_new(&d); end = label_new(&d);
    emit_set_const(&d, 0, 3);
    emit_switch(&d, 0, 2, 0);
    emit_case(&d, 1, one);
    emit_case(&d, 2, two);
    label_place(&d, def);
    emit_set_const(&d, 1, 111);
    emit_jump(&d, end);
    label_place(&d, one);
    emit_set_const(&d, 1, 1);
    emit_jump(&d, end);
    label_place(&d, two);
    emit_set_const(&d, 1, 2);
    label_place(&d, end);
    emit_stop(&d);
    code_finalize(&d);

    status = run_code(0, d.bytes, NULL);
    check_true("switch.default.run", status == RUNNER_DONE, "runner did not finish");
    check_eq("switch.default", script_memory[1], 111);
}

static void test_threads(void) {
    Code c;
    code_init(&c);
    int thread1 = label_new(&c), thread2 = label_new(&c);
    emit_beginthread(&c, 0, thread1, 8, 0);
    emit_beginthread(&c, 0, thread2, 9, 0);
    emit_join(&c, 8);
    emit_join(&c, 9);
    emit_set_const(&c, 10, 1);
    emit_stop(&c);

    label_place(&c, thread1);
    emit_set_const(&c, 1, 0x11);
    emit_idle(&c);
    emit_set_const(&c, 2, 0x12);
    emit_stop(&c);

    label_place(&c, thread2);
    emit_set_const(&c, 3, 0x21);
    emit_idle(&c);
    emit_set_const(&c, 4, 0x22);
    emit_stop(&c);
    code_finalize(&c);

    UBYTE status = run_code(0, c.bytes, NULL);
    check_true("threads.run", status == RUNNER_DONE, "runner did not finish");
    check_eq("threads.one_a", script_memory[1], 0x11);
    check_eq("threads.one_b", script_memory[2], 0x12);
    check_eq("threads.two_a", script_memory[3], 0x21);
    check_eq("threads.two_b", script_memory[4], 0x22);
    check_eq("threads.main", script_memory[10], 1);
    check_true("threads.joined", (script_memory[8] & SCRIPT_TERMINATED) != 0 && (script_memory[9] & SCRIPT_TERMINATED) != 0, "thread handle not terminated");
}

static void test_terminate(void) {
    Code c;
    code_init(&c);
    int victim = label_new(&c);
    emit_beginthread(&c, 0, victim, 8, 0);
    emit_terminate(&c, 8);
    emit_set_const(&c, 10, 1);
    emit_stop(&c);
    label_place(&c, victim);
    emit_set_const(&c, 1, 99);
    emit_stop(&c);
    code_finalize(&c);

    UBYTE status = run_code(0, c.bytes, NULL);
    check_true("terminate.run", status == RUNNER_DONE, "runner did not finish");
    check_eq("terminate.main", script_memory[10], 1);
    check_eq("terminate.child_skipped", script_memory[1], 0);
}

static int run_invoke(UWORD frames, int *updates) {
    Code c;
    code_init(&c);
    emit_set_const(&c, 0, frames);
    emit_invoke(&c, 0, 0, 0, 0);
    emit_set_const(&c, 1, 1);
    emit_stop(&c);
    code_finalize(&c);
    UBYTE status = run_code(0, c.bytes, updates);
    return status == RUNNER_DONE && script_memory[1] == 1;
}

static void test_invoke(void) {
    int updates0 = 0, updates3 = 0;
    int ok0 = run_invoke(0, &updates0);
    int ok3 = run_invoke(3, &updates3);
    check_true("invoke.zero", ok0, "wait_frames(0) did not complete");
    check_true("invoke.three", ok3, "wait_frames(3) did not complete");
    check_true("invoke.frame_count", updates3 > updates0, "wait_frames did not wait for frames");
    check_eq("invoke.zero_updates", updates0, 1);
}

static void test_memory_ops(void) {
    Code c;
    code_init(&c);
    for (int i = 0; i < 5; i++) emit_set_const(&c, i, 0x1000 + i);
    emit_memcpy(&c, 10, 0, 5);
    emit_memset(&c, 20, 0x7777, 3);
    emit_stop(&c);
    code_finalize(&c);

    UBYTE status = run_code(0, c.bytes, NULL);
    check_true("memory_ops.run", status == RUNNER_DONE, "runner did not finish");
    check_eq("memory_ops.memcpy0", script_memory[10], 0x1000);
    check_eq("memory_ops.memcpy4", script_memory[14], 0x1004);
    check_eq("memory_ops.memset0", script_memory[20], 0x7777);
    check_eq("memory_ops.memset2", script_memory[22], 0x7777);
    check_eq("memory_ops.memset_stop", script_memory[23], 0);
}

static void build_rng(Code *c, UWORD seed) {
    code_init(c);
    emit_set_const(c, 0, seed);
    emit_init_rng(c, 0);
    emit_rand(c, 1, 10, 100);
    emit_rand(c, 2, 10, 100);
    emit_rand(c, 3, 10, 100);
    emit_stop(c);
    code_finalize(c);
}

static void test_rng(void) {
    Code c;
    UWORD first[3], second[3];
    build_rng(&c, 0x1234);
    UBYTE status = run_code(0, c.bytes, NULL);
    check_true("rng.first_run", status == RUNNER_DONE, "runner did not finish");
    for (int i = 0; i < 3; i++) first[i] = script_memory[1 + i];

    status = run_code(0, c.bytes, NULL);
    check_true("rng.second_run", status == RUNNER_DONE, "runner did not finish");
    for (int i = 0; i < 3; i++) second[i] = script_memory[1 + i];

    check_true("rng.deterministic", memcmp(first, second, sizeof(first)) == 0, "same seed produced different values");
    int in_range = 1;
    for (int i = 0; i < 3; i++) in_range &= first[i] >= 10 && first[i] < 110;
    check_true("rng.range", in_range, "random value outside [min, min+limit)");
}

static void test_unimplemented(void) {
    static UBYTE bad[] = { 0x30, 0x00 };
    vm_last_unimplemented_opcode = 0;
    host_banks[0] = bad;
    script_runner_init(1);
    check_true("unimplemented.start", script_execute(0, bad, NULL, 0) != NULL, "script_execute failed");
    UBYTE status = script_runner_update();
    check_true("unimplemented.stops", status == RUNNER_DONE, "context did not stop");
    check_eq("unimplemented.opcode", vm_last_unimplemented_opcode, 0x30);
}

int main(void) {
    test_push_pop();
    test_indirect();
    test_rpn();
    test_branches();
    test_call_far();
    test_loop();
    test_switch();
    test_threads();
    test_terminate();
    test_invoke();
    test_memory_ops();
    test_rng();
    test_unimplemented();

    printf("%d passed, %d failed\n", checks_passed, checks_failed);
    return checks_failed ? 1 : 0;
}
