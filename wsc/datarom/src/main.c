/* WSC data path test: read every exported scene through bankdata helpers.
 *
 * Nothing here dereferences exported data directly. Scene objects, arrays and
 * far_ptr_t members are read with ReadBankedFarPtr/ReadBankedUWORD/
 * ReadBankedUBYTE, and the scene init opcode goes through vm_bank_base().
 * The resulting word sequence is the oracle's RAM table.
 */

#include <stddef.h>
#include <stdint.h>

#include "gbs_types.h"
#include "bankdata.h"
#include "d2c_manifest.h"
#include "d2c_scripts.h"

#define DATAROM_MAX_RESULTS 1024

uint16_t datarom_results[DATAROM_MAX_RESULTS];
uint16_t datarom_result_count;
uint16_t datarom_done;

static const struct scene_t __far *const datarom_scenes[D2C_SCENE_COUNT] = {
    D2C_SCENE_LIST
};

/* Script banks are 1-based, so slot 0 stays unused. */
static const uint8_t __far *const datarom_banks[S2C_BANK_COUNT + 1] = {
    (const uint8_t __far *)0,
    D2C_BANK_LIST
};

const uint8_t __far *vm_bank_base(UBYTE bank) {
    return (bank >= 1 && bank <= S2C_BANK_COUNT)
        ? datarom_banks[bank] : (const uint8_t __far *)0;
}

static UBYTE read_u8(const void __far *base, size_t offset, UBYTE bank) {
    return ReadBankedUBYTE((const UBYTE __far *)base + offset, bank);
}

static UWORD read_u16(const void __far *base, size_t offset, UBYTE bank) {
    return ReadBankedUWORD((const UBYTE __far *)base + offset, bank);
}

static far_ptr_t read_far_ptr(const void __far *base, size_t offset) {
    far_ptr_t value;
    ReadBankedFarPtr(&value, (const UBYTE __far *)base + offset, 0);
    return value;
}

static void put(UWORD value) {
    if (datarom_result_count < DATAROM_MAX_RESULTS)
        datarom_results[datarom_result_count++] = value;
}

static void read_scene(const struct scene_t __far *scene) {
    UBYTE width, height, n_actors, n_triggers;
    far_ptr_t background, actors, triggers, init;
    UBYTE bank = 0;
    UWORD i;

    width = read_u8(scene, offsetof(scene_t, width), bank);
    height = read_u8(scene, offsetof(scene_t, height), bank);
    n_actors = read_u8(scene, offsetof(scene_t, n_actors), bank);
    n_triggers = read_u8(scene, offsetof(scene_t, n_triggers), bank);
    put(width);
    put(height);
    put(n_actors);
    put(n_triggers);

    background = read_far_ptr(scene, offsetof(scene_t, background));
    {
        UBYTE bg_width = read_u8(background.ptr, offsetof(background_t, width),
                                 background.bank);
        UBYTE bg_height = read_u8(background.ptr,
                                  offsetof(background_t, height),
                                  background.bank);
        far_ptr_t tileset = read_far_ptr(background.ptr,
                                         offsetof(background_t, tileset));
        far_ptr_t tilemap = read_far_ptr(background.ptr,
                                         offsetof(background_t, tilemap));
        UWORD n_tiles = read_u16(tileset.ptr, offsetof(tileset_t, n_tiles),
                                 tileset.bank);
        UWORD last = (UWORD)bg_width * bg_height - 1;

        put(n_tiles);
        put(read_u8(tilemap.ptr, 0, tilemap.bank));
        put(read_u8(tilemap.ptr, last, tilemap.bank));
    }

    init = read_far_ptr(scene, offsetof(scene_t, script_init));
    {
        const uint8_t __far *base = vm_bank_base(init.bank);
        UWORD offset = (UWORD)((const uint8_t __far *)init.ptr - base);
        put(read_u8(base, offset, init.bank));
    }

    actors = read_far_ptr(scene, offsetof(scene_t, actors));
    for (i = 0; i < n_actors; i++) {
        const UBYTE __far *actor = (const UBYTE __far *)actors.ptr +
                                   (UWORD)i * sizeof(actor_t);
        put(read_u16(actor, offsetof(actor_t, pos.x), actors.bank));
        put(read_u16(actor, offsetof(actor_t, pos.y), actors.bank));
    }

    triggers = read_far_ptr(scene, offsetof(scene_t, triggers));
    for (i = 0; i < n_triggers; i++) {
        const UBYTE __far *trigger = (const UBYTE __far *)triggers.ptr +
                                     (UWORD)i * sizeof(trigger_t);
        put(read_u8(trigger, offsetof(trigger_t, left), triggers.bank));
        put(read_u8(trigger, offsetof(trigger_t, top), triggers.bank));
        put(read_u8(trigger, offsetof(trigger_t, right), triggers.bank));
        put(read_u8(trigger, offsetof(trigger_t, bottom), triggers.bank));
    }
}

int main(void) {
    UWORD i;

    for (i = 0; i < D2C_SCENE_COUNT; i++)
        read_scene(datarom_scenes[i]);

    datarom_done = 1;
    for (;;) {
    }
}
