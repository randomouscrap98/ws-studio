/* 12 far read-only chunks, one per 64 KiB linear bank. */
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

.section .farrodata.reach8, "a"
.globl chunk8
chunk8:
    .byte 0x88
    .fill 64510, 1, 0x00
    .byte 0x77

.section .farrodata.reach9, "a"
.globl chunk9
chunk9:
    .byte 0x89
    .fill 64510, 1, 0x00
    .byte 0x76

.section .farrodata.reach10, "a"
.globl chunk10
chunk10:
    .byte 0x8A
    .fill 64510, 1, 0x00
    .byte 0x75

.section .farrodata.reach11, "a"
.globl chunk11
chunk11:
    .byte 0x8B
    .fill 64510, 1, 0x00
    .byte 0x74
