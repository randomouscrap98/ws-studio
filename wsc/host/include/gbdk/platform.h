#ifndef WS_HOST_GBDK_PLATFORM_H
#define WS_HOST_GBDK_PLATFORM_H

/* Minimal GBDK platform shim for building GBVM on the host. */

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

typedef uint8_t UBYTE;
typedef int8_t BYTE;
typedef uint16_t UWORD;
typedef int16_t WORD;
typedef uint8_t UINT8;
typedef int8_t INT8;
typedef uint16_t UINT16;
typedef int16_t INT16;
typedef uint32_t UINT32;
typedef int32_t INT32;

#ifndef TRUE
#define TRUE 1
#endif
#ifndef FALSE
#define FALSE 0
#endif

#define BANKED
#define NONBANKED
#define NAKED
#define OLDCALL
#define PRESERVES_REGS(...)
#define SFR
#define AT(addr)
#define BANK(name) 0
#define BANKREF(name)
#define BANKREF_EXTERN(name)
#define SWITCH_ROM(bank) ((void)(bank))
#define CURRENT_BANK 0

extern UWORD sys_time;
void wait_vbl_done(void);

#endif
