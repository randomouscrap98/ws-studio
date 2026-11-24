/* Product boot hook: keep the start scene and position from the exported
 * project. The generated bootstrap calls this before the first scene load;
 * the test image overrides the start scene here instead. */

#include <stdint.h>

#include "gbs_types.h"

void wsc_boot_select(far_ptr_t *scene, INT16 *x, INT16 *y) {
    (void)scene;
    (void)x;
    (void)y;
}
