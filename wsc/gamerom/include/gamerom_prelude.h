#ifndef GAMEROM_PRELUDE_H
#define GAMEROM_PRELUDE_H

/* Forced include for the WSC engine boot ROM. The exported palette C uses
 * GBDK's RGB() macro, which is not in the minimal platform shim. */

#include <stdint.h>

#ifndef RGB
#define RGB(r, g, b) ((uint16_t)((((b) & 0x1f) << 10) | \
                                 (((g) & 0x1f) << 5) | ((r) & 0x1f)))
#endif

#endif
