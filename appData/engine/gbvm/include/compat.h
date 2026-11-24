#ifndef _COMPAT_H_INCLUDE
#define _COMPAT_H_INCLUDE

/* The only spelling of "far on WSC, nothing elsewhere". */
#ifdef __ia16__
#define FAR __far
/* Plain engine state that is not touched by the display hardware can live in
 * the colour-only IRAM bank. 0xC000 is above the C18 tile area
 * (0x4000..0xBFFF) and below the hardware palettes (0xFE00..0xFFFF). */
#define WSC_UPPER_RAM __attribute__((section(".iramC_C000")))
#else
#define FAR
#define WSC_UPPER_RAM
#endif

#ifndef OLDCALL
#if __SDCC_REVISION >= 12608
#define OLDCALL __sdcccall(0)
#else
#define OLDCALL
#endif
#endif

#ifndef PRESERVES_REGS
#ifdef __SDCC
#define PRESERVES_REGS(...) __preserves_regs(__VA_ARGS__)
#else
#define PRESERVES_REGS(...)
#endif
#endif

#ifndef NAKED
#ifdef __SDCC
#define NAKED   __naked
#else
#define NAKED
#endif
#endif

#ifndef SFR
#ifdef __SDCC
#define SFR     __sfr
#else
#define SFR
#endif
#endif

#ifndef AT
#ifdef __SDCC
#define AT(A)   __at(A)
#else
#define AT(A)
#endif
#endif

#ifndef FASTUBYTE
#if defined(__SDCC) && defined(NINTENDO)
#define FASTUBYTE SFR
#else
#define FASTUBYTE UBYTE
#endif
#endif

#endif