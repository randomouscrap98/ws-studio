#pragma bank 255

#include <string.h>

#include "load_save.h"

#include "system.h"
#include "actor.h"
#include "vm.h"
#include "events.h"
#include "music_manager.h"
#include "data_manager.h"
#ifdef BATTERYLESS
    #include "bankdata.h"
    #include "flasher.h"
#endif
#ifdef __ia16__
    #include "hal.h"
    typedef UBYTE __far *sram_ptr_t;
#else
    typedef UBYTE *sram_ptr_t;
#endif

/* SRAM-only value accesses.  On WSC the save data pointer is a far pointer
 * into segment 0x1000, so the plain GB expressions would need the DS changed
 * for every access.  The HAL copies bulk data; the scalar accesses below
 * just use the matching far pointer type. */
#ifdef __ia16__
#define SIGN_BY_PTR(ptr) (*((UINT32 __far *)(ptr)))
#define SRAM_READ_SIZE(ptr) (*((const size_t __far *)(ptr)))
#define SRAM_WRITE_SIZE(ptr, v) (*((size_t __far *)(ptr)) = (v))
#define SRAM_READ_U8(ptr) (*((const uint8_t __far *)(ptr)))
#define SRAM_WRITE_U8(ptr, v) (*((uint8_t __far *)(ptr)) = (v))
#define SRAM_BASE(bank) ((sram_ptr_t)hal_sram_select(bank))
#define SRAM_COPY_TO(dst, src, n) hal_sram_copy_to((dst), (src), (n))
#define SRAM_COPY_FROM(dst, src, n) hal_sram_copy_from((dst), (src), (n))
#else
#define SIGN_BY_PTR(ptr) *((UINT32 *)(ptr))
#define SRAM_READ_SIZE(ptr) (*((const size_t *)(ptr)))
#define SRAM_WRITE_SIZE(ptr, v) (*((size_t *)(ptr)) = (v))
#define SRAM_READ_U8(ptr) (*((const uint8_t *)(ptr)))
#define SRAM_WRITE_U8(ptr, v) (*((uint8_t *)(ptr)) = (v))
#define SRAM_BASE(bank) ((sram_ptr_t)(0xA000u))
#define SRAM_COPY_TO(dst, src, n) memcpy((dst), (src), (n))
#define SRAM_COPY_FROM(dst, src, n) memcpy((dst), (src), (n))
#endif

#ifdef __ia16__
/* d2c generates the signature as far const ROM data on WSC. */
extern const UINT32 __far save_signature;
#else
extern const UINT32 save_signature;
#endif

typedef struct save_point_t {
    void * target;
    size_t size;
    uint8_t id;
} save_point_t;

#define SAVEPOINT(A, ID) {&(A), sizeof(A), (ID)}
#define SAVEPOINTS_END {0, 0}

extern uint16_t __rand_seed;

const save_point_t save_points[] = {
    // variables (must be first, need for peeking)
    SAVEPOINT(script_memory, 0),
    // VM contexts
    SAVEPOINT(CTXS, 1),
    SAVEPOINT(first_ctx, 2), SAVEPOINT(free_ctxs, 3), SAVEPOINT(old_executing_ctx, 4), SAVEPOINT(executing_ctx, 5), SAVEPOINT(vm_lock_state, 6),
    // intupt events
    SAVEPOINT(input_events, 7), SAVEPOINT(input_slots, 8),
    // timers
    SAVEPOINT(timer_events, 9), SAVEPOINT(timer_values, 10),
    // music
    SAVEPOINT(music_current_track_bank, 11),
    SAVEPOINT(music_current_track, 12),
    SAVEPOINT(music_events, 13),
    // scene
    SAVEPOINT(current_scene, 14), SAVEPOINT(scene_stack_ptr, 15), SAVEPOINT(scene_stack, 16),
    // actors
    SAVEPOINT(actors, 17),
    SAVEPOINT(actors_active_head, 18), SAVEPOINT(actors_inactive_head, 19), SAVEPOINT(player_moving, 20), SAVEPOINT(player_collision_actor, 21),
    // system
    SAVEPOINT(__rand_seed, 22),
    // terminator
    SAVEPOINTS_END
};

#ifdef BATTERYLESS
    extern void _start_save;
#endif

size_t save_blob_size;

void data_init(void) BANKED {
#ifdef __ia16__
    hal_sram_init();
#else
    ENABLE_RAM_MBC5;
    SWITCH_RAM_BANK(0, RAM_BANKS_ONLY);
#endif
    // calculate save blob size
    save_blob_size = sizeof(save_signature) + sizeof(save_blob_size);
    for(const save_point_t * point = save_points; (point->target); point++) {
        save_blob_size += sizeof(point->size) + sizeof(point->id) + point->size;
    }
#ifdef BATTERYLESS
    // load from FLASH ROM
    for (UBYTE i = 0; i < SRAM_BANKS_TO_SAVE; i++) restore_sram_bank(i);
#endif
}

sram_ptr_t data_slot_address(UBYTE slot, UBYTE *bank) {
    UWORD res = 0, res_bank = 0;
    for (UBYTE i = 0; i < slot; i++) {
        res += save_blob_size;
        if ((res + save_blob_size) > SRAM_BANK_SIZE) {
            if (++res_bank >= SRAM_BANKS_TO_SAVE) return NULL;
            res = 0;
        }
    }
    *bank = res_bank;
    return SRAM_BASE(res_bank) + res;
}

void data_save(UBYTE slot) BANKED {
    UBYTE data_bank;
    sram_ptr_t save_data = data_slot_address(slot, &data_bank);
    if (save_data == NULL) return;
    SWITCH_RAM_BANK(data_bank, RAM_BANKS_ONLY);

    // signature
    SIGN_BY_PTR(save_data) = save_signature;
    save_data += sizeof(save_signature);
    // size of the save blob
    SRAM_WRITE_SIZE(save_data, save_blob_size);
    save_data += sizeof(save_blob_size);
    for(const save_point_t * point = save_points; (point->target); point++) {
        // size of the block
        SRAM_WRITE_SIZE(save_data, point->size);
        save_data += sizeof(point->size);
        // ID of the block
        SRAM_WRITE_U8(save_data, point->id);
        save_data += sizeof(point->id);
        // block data
        SRAM_COPY_TO(save_data, point->target, point->size);
        save_data += point->size;
    }
#ifdef BATTERYLESS
    // save to FLASH ROM
    save_sram(SRAM_BANKS_TO_SAVE);
#endif
}

UBYTE data_load(UBYTE slot) BANKED {
    UBYTE data_bank;
    sram_ptr_t save_data = data_slot_address(slot, &data_bank);
    if (save_data == NULL) return FALSE;
    SWITCH_RAM_BANK(data_bank, RAM_BANKS_ONLY);
    if (SIGN_BY_PTR(save_data) != save_signature) return FALSE;
    // seek to the first block
    save_data += sizeof(save_signature) + sizeof(save_blob_size);
    // load blocks
    for(const save_point_t * point = save_points; (point->target); point++) {
        // check chunk size
        if (SRAM_READ_SIZE(save_data) != point->size) return FALSE; else save_data += sizeof(point->size);
        // check chunk id
        if (SRAM_READ_U8(save_data) != point->id) return FALSE; else save_data += sizeof(point->id);
        // copy chunk data
        SRAM_COPY_FROM(point->target, save_data, point->size);
        save_data += point->size;
    }
    // Restart music
    if (music_current_track_bank != MUSIC_STOP_BANK) {
        music_next_track = music_current_track;
    } else {
        music_sound_cut();
    }
    return TRUE;
}

void data_clear(UBYTE slot) BANKED {
    UBYTE data_bank;
    sram_ptr_t save_data = data_slot_address(slot, &data_bank);
    if (save_data == NULL) return;
    SWITCH_RAM_BANK(data_bank, RAM_BANKS_ONLY);
    SIGN_BY_PTR(save_data) = 0;
#ifdef BATTERYLESS
    // save to FLASH ROM
    save_sram(SRAM_BANKS_TO_SAVE);
#endif
}

UBYTE data_peek(UBYTE slot, UINT16 idx, UWORD count, UINT16 * dest) BANKED {
    UBYTE data_bank;
    sram_ptr_t save_data = data_slot_address(slot, &data_bank);
    if (save_data == NULL) return FALSE;
    SWITCH_RAM_BANK(data_bank, RAM_BANKS_ONLY);
    if (SIGN_BY_PTR(save_data) != save_signature) return FALSE;
    save_data += (sizeof(save_signature) + sizeof(save_blob_size) + sizeof(size_t) + sizeof(uint8_t)) + (idx << 1);
    if (count) SRAM_COPY_FROM(dest, save_data, count << 1);
    return TRUE;
}
