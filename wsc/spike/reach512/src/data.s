/* 8 far read-only chunks, one per 64 KiB linear bank. */
.section .farrodata.reach0, "a"
.globl chunk0
chunk0:
    .byte 0x80
    .fill 64510, 1, 0x00
    .byte 0x7F

.section .farrodata.reach1, "a"
.globl chunk1
chunk1:
    .byte 0x81
    .fill 64510, 1, 0x00
    .byte 0x7E

.section .farrodata.reach2, "a"
.globl chunk2
chunk2:
    .byte 0x82
    .fill 64510, 1, 0x00
    .byte 0x7D

.section .farrodata.reach3, "a"
.globl chunk3
chunk3:
    .byte 0x83
    .fill 64510, 1, 0x00
    .byte 0x7C

.section .farrodata.reach4, "a"
.globl chunk4
chunk4:
    .byte 0x84
    .fill 64510, 1, 0x00
    .byte 0x7B

.section .farrodata.reach5, "a"
.globl chunk5
chunk5:
    .byte 0x85
    .fill 64510, 1, 0x00
    .byte 0x7A

.section .farrodata.reach6, "a"
.globl chunk6
chunk6:
    .byte 0x86
    .fill 64510, 1, 0x00
    .byte 0x79

.section .farrodata.reach7, "a"
.globl chunk7
chunk7:
    .byte 0x87
    .fill 64510, 1, 0x00
    .byte 0x78
