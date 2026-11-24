/*
 * ROM capacity filler, compiled only into the capacity_check.sh variant
 * (CAPACITY_FILLER=1, which defines WSC_CAPACITY_TEST).
 *
 * The normal build must stay unchanged. The variant adds:
 *   - 48 KiB of far code (a single reachable function full of NOPs), and
 *   - 150 KiB of far const data in five 30000-byte sections.
 *
 * A constructor calls the code and reads the first and last byte of every
 * data block, so Wonderful's section garbage collection keeps all of it.
 * C objects cannot exceed 32767 bytes, which is why the data and code are
 * emitted as assembly sections.
 */

#ifdef WSC_CAPACITY_TEST

#include <stdint.h>

#define FILLER_CODE_BYTES       49152
#define FILLER_DATA_BLOCK_BYTES 30000

#define STR_(x) #x
#define STR(x)  STR_(x)

extern const uint8_t __far capacity_data_0[];
extern const uint8_t __far capacity_data_1[];
extern const uint8_t __far capacity_data_2[];
extern const uint8_t __far capacity_data_3[];
extern const uint8_t __far capacity_data_4[];

void capacity_filler_code(void);

static volatile uint8_t capacity_sink;

__asm__(
    ".section .fartext.capacity_filler,\"ax\",@progbits\n"
    ".globl capacity_filler_code\n"
    ".type capacity_filler_code, @function\n"
    "capacity_filler_code:\n"
    ".rept " STR(FILLER_CODE_BYTES) "\n"
    "nop\n"
    ".endr\n"
    "lret\n"
    ".size capacity_filler_code, . - capacity_filler_code\n"
    ".previous\n");

#define CAPACITY_DATA_SECTION(n)                                        \
    __asm__(                                                            \
        ".section .farrodata.capacity_data_" #n ",\"a\",@progbits\n"    \
        ".globl capacity_data_" #n "\n"                                 \
        ".type capacity_data_" #n ", @object\n"                         \
        "capacity_data_" #n ":\n"                                       \
        ".space " STR(FILLER_DATA_BLOCK_BYTES) ", 0xA5\n"               \
        ".size capacity_data_" #n ", . - capacity_data_" #n "\n"        \
        ".previous\n")

CAPACITY_DATA_SECTION(0);
CAPACITY_DATA_SECTION(1);
CAPACITY_DATA_SECTION(2);
CAPACITY_DATA_SECTION(3);
CAPACITY_DATA_SECTION(4);

__attribute__((constructor))
static void capacity_filler_init(void)
{
    capacity_filler_code();

    capacity_sink = capacity_data_0[0];
    capacity_sink = capacity_data_0[FILLER_DATA_BLOCK_BYTES - 1];
    capacity_sink = capacity_data_1[0];
    capacity_sink = capacity_data_1[FILLER_DATA_BLOCK_BYTES - 1];
    capacity_sink = capacity_data_2[0];
    capacity_sink = capacity_data_2[FILLER_DATA_BLOCK_BYTES - 1];
    capacity_sink = capacity_data_3[0];
    capacity_sink = capacity_data_3[FILLER_DATA_BLOCK_BYTES - 1];
    capacity_sink = capacity_data_4[0];
    capacity_sink = capacity_data_4[FILLER_DATA_BLOCK_BYTES - 1];
}

#endif /* WSC_CAPACITY_TEST */
