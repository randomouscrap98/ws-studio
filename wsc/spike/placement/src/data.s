/* Two 40 KiB far read-only sections, each with distinct end markers. */
.section .farrodata.place_a, "a"
.globl far_a
far_a:
    .byte 0xA1
    .fill 40958, 1, 0x00
    .byte 0xA2

.section .farrodata.place_b, "a"
.globl far_b
far_b:
    .byte 0xB1
    .fill 40958, 1, 0x00
    .byte 0xB2

/* Forced into ROM bank 0 via a .rom0_<bank> section name. */
.section .rom0_1.forced, "a"
.globl forced
forced:
    .byte 0xC1
    .fill 15, 1, 0x00
