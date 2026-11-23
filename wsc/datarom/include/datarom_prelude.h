#ifndef DATAROM_PRELUDE_H
#define DATAROM_PRELUDE_H

/* Forced include for the WSC data-path ROM. The exported palette C uses
 * GBDK's RGB() macro, which lives in GBDK's cgb.h rather than in the minimal
 * platform shim used by the other WSC ROMs. */

#include <stdint.h>

#ifndef RGB
#define RGB(r, g, b) ((uint16_t)((((b) & 0x1f) << 10) | \
                                 (((g) & 0x1f) << 5) | ((r) & 0x1f)))
#endif

#endif
