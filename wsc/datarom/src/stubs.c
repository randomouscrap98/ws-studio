/* Test-only engine stubs for the data-path ROM.
 *
 * Exported music data stores routine pointers in hUGESong_t. The WSC data
 * test never plays music, so a single empty tracker routine satisfies the
 * link. The real audio engine is a later port.
 */

#include "hUGEDriver.h"

void hUGETrackerRoutine(unsigned char tick, unsigned int param) {
    (void)tick;
    (void)param;
}
