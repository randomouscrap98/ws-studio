/* A 96 KiB far read-only section: six 16 KiB quarters with distinct bytes.
 * This is larger than one 64 KiB segment; wf-wswantool must split it. */
.section .farrodata.big, "a"
.globl big
big:
    .fill 16384, 1, 0x11
    .fill 16384, 1, 0x22
    .fill 16384, 1, 0x33
    .fill 16384, 1, 0x44
    .fill 16384, 1, 0x55
    .fill 16384, 1, 0x66
