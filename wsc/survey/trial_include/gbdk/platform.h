#ifndef WS_SURVEY_GBDK_PLATFORM_H
#define WS_SURVEY_GBDK_PLATFORM_H

/*
 * Trial-build GBDK shim for the C05s hardware survey.
 *
 * This is not a port of GBDK. It declares just enough of the GBDK 2020 API
 * and the Game Boy hardware register names for the engine sources to reach
 * the compiler's real diagnostics. A successful compile here means "no
 * non-GBDK portability problem was found", not "this file runs on WSC".
 */

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
typedef uint8_t BOOLEAN;

#ifndef TRUE
#define TRUE 1
#endif
#ifndef FALSE
#define FALSE 0
#endif

/* GBDK attributes and calling conventions.  The WSC build sees the same
 * empty definitions as wsc/host/include/gbdk/platform.h. */
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
#define SWITCH_RAM(bank) ((void)(bank))
#define CURRENT_BANK 0
#define CRITICAL
#define ENABLE_RAM
#define DISABLE_RAM
#define ENABLE_RAM_MBC5
#define DISABLE_RAM_MBC5

/* Screen/device constants. */
#define DEVICE_SCREEN_WIDTH 20
#define DEVICE_SCREEN_HEIGHT 18
#define DEVICE_SCREEN_PX_WIDTH 160
#define DEVICE_SCREEN_PX_HEIGHT 144
#define DEVICE_WINDOW_PX_OFFSET_X 7
#define MAXWNDPOSY 143
#define SCREENWIDTH 160
#define SCREENHEIGHT 144
#define SCREENWIDTH_PX 160
#define SCREENHEIGHT_PX 144
#define MAX_HARDWARE_SPRITES 40
#define MAX_SPRITES 40

/* Keypad bits. */
#define J_RIGHT 0x01
#define J_LEFT 0x02
#define J_UP 0x04
#define J_DOWN 0x08
#define J_A 0x10
#define J_B 0x20
#define J_SELECT 0x40
#define J_START 0x80

/* LCDC / STAT bits. */
#define LCDCF_OFF 0x00
#define LCDCF_ON 0x80
#define LCDCF_BG8000 0x00
#define LCDCF_BG8800 0x10
#define LCDCF_BG9800 0x00
#define LCDCF_BG9C00 0x08
#define LCDCF_WIN9800 0x00
#define LCDCF_WIN9C00 0x40
#define LCDCF_WINON 0x20
#define LCDCF_OBJOFF 0x00
#define LCDCF_OBJON 0x02
#define LCDCF_OBJ8 0x00
#define LCDCF_OBJ16 0x04
#define LCDCF_BGON 0x01
#define STATF_LYC 0x40
#define STATF_B_BUSY 0x02
#define STATF_BUSY 0x02

/* Interrupt bits. */
#define VBL_IFLAG 0x01
#define LCD_IFLAG 0x02
#define TIM_IFLAG 0x04
#define SIO_IFLAG 0x08
#define JOY_IFLAG 0x10

/* CGB VRAM banks. */
#define VBK_BANK_0 0
#define VBK_BANK_1 1
#define VBK_TILES 0
#define VBK_ATTRIBUTES 1

/* Convenience LCDC setters from GBDK. */
#define DISPLAY_ON (LCDC_REG |= LCDCF_ON)
#define DISPLAY_OFF (LCDC_REG &= (UBYTE)~LCDCF_ON)
#define SHOW_BKG (LCDC_REG |= LCDCF_BGON)
#define HIDE_BKG (LCDC_REG &= (UBYTE)~LCDCF_BGON)
#define SHOW_WIN (LCDC_REG |= LCDCF_WINON)
#define HIDE_WIN (LCDC_REG &= (UBYTE)~LCDCF_WINON)
#define SHOW_SPRITES (LCDC_REG |= LCDCF_OBJON)
#define HIDE_SPRITES (LCDC_REG &= (UBYTE)~LCDCF_OBJON)
#define SPRITES_8x8 (LCDC_REG &= (UBYTE)~LCDCF_OBJ16)
#define SPRITES_8x16 (LCDC_REG |= LCDCF_OBJ16)

/* CPU types. */
#define DMG_TYPE 0x01
#define MGB_TYPE 0x02
#define CGB_TYPE 0x10
#define SGB_TYPE 0x20

/* Hardware register names used by the engine. */
extern volatile UBYTE LCDC_REG;
extern volatile UBYTE STAT_REG;
extern volatile UBYTE SCY_REG;
extern volatile UBYTE SCX_REG;
extern volatile UBYTE LY_REG;
extern volatile UBYTE LYC_REG;
extern volatile UBYTE WY_REG;
extern volatile UBYTE WX_REG;
extern volatile UBYTE BGP_REG;
extern volatile UBYTE OBP0_REG;
extern volatile UBYTE OBP1_REG;
extern volatile UBYTE VBK_REG;
extern volatile UBYTE IE_REG;
extern volatile UBYTE IF_REG;
extern volatile UBYTE DIV_REG;
extern volatile UBYTE TMA_REG;
extern volatile UBYTE TAC_REG;
extern volatile UBYTE KEY1_REG;
extern volatile UBYTE SB_REG;
extern volatile UBYTE SC_REG;
extern volatile UBYTE BCPS_REG_ADDR;
extern volatile UBYTE BCPD_REG_ADDR;
extern volatile UBYTE OCPS_REG_ADDR;
extern volatile UBYTE OCPD_REG_ADDR;
extern volatile UBYTE NR10_REG;
extern volatile UBYTE NR11_REG;
extern volatile UBYTE NR12_REG;
extern volatile UBYTE NR13_REG;
extern volatile UBYTE NR14_REG;
extern volatile UBYTE NR21_REG;
extern volatile UBYTE NR22_REG;
extern volatile UBYTE NR23_REG;
extern volatile UBYTE NR24_REG;
extern volatile UBYTE NR30_REG;
extern volatile UBYTE NR31_REG;
extern volatile UBYTE NR32_REG;
extern volatile UBYTE NR33_REG;
extern volatile UBYTE NR34_REG;
extern volatile UBYTE NR41_REG;
extern volatile UBYTE NR42_REG;
extern volatile UBYTE NR43_REG;
extern volatile UBYTE NR44_REG;
extern volatile UBYTE NR50_REG;
extern volatile UBYTE NR51_REG;
extern volatile UBYTE NR52_REG;
extern volatile UBYTE __AUD3WAVERAM[16];

/* Banking / SRAM state. */
extern volatile UBYTE _current_ram_bank;
extern volatile UBYTE __current_bank;
extern volatile UBYTE _current_bank;
extern volatile UBYTE _cpu;
extern UBYTE _is_GBA;
extern UBYTE _is_CGB;
extern UBYTE _is_SGB;
extern volatile UBYTE _map_tile_offset;
extern UWORD sys_time;

typedef struct joypads_t {
    UBYTE npads;
    UBYTE joy0;
    UBYTE joy1;
    UBYTE joy0_pressed;
    UBYTE joy1_pressed;
    UBYTE joypads[2];
} joypads_t;

/* SIO status values from GBDK's serial helpers. */
#define IO_IDLE 0x00
#define IO_SENDING 0x01
#define IO_RECEIVING 0x02
#define IO_ERROR 0x04
#define DT_IDLE 0x00
#define DT_RECEIVING 0xFF

/* SGB command ids. */
#define SGB_MASK_EN 0x17
#define SGB_CHR_TRN 0x13
#define SGB_PCT_TRN 0x14

/* GBDK API used by the engine. */
void display_off(void);
void display_on(void);
void wait_vbl_done(void);
void cpu_fast(void);
void cpu_slow(void);
void delay(UINT8 frames);

void add_VBL(void (*isr)(void));
void add_LCD(void (*isr)(void));
void add_TIM(void (*isr)(void));
void add_SIO(void (*isr)(void));
void remove_VBL(void (*isr)(void));
void remove_LCD(void (*isr)(void));
void remove_TIM(void (*isr)(void));
void remove_SIO(void (*isr)(void));
void set_interrupts(UBYTE flags);
void enable_interrupts(void);
void disable_interrupts(void);

UBYTE joypad(void);
void joypad_init(UBYTE npads, void *joypads);
void joypad_ex(void *joypads);
void waitpad(UBYTE mask);
void waitpadup(void);

void initrand(UWORD seed);
UWORD randw(void);
void initarand(UWORD seed);
UWORD arand(void);

void sgb_transfer(void *data);
UBYTE sgb_check(void);

void set_bkg_data(UINT8 first, UINT8 count, const void *data);
void set_bkg_tiles(UINT8 x, UINT8 y, UINT8 w, UINT8 h, const void *tiles);
void set_bkg_submap_attributes(UINT8 x, UINT8 y, UINT8 w, UINT8 h, const void *map, UINT8 map_w);
void set_bkg_palette(UINT8 first, UINT8 count, const void *palettes);
void set_win_data(UINT8 first, UINT8 count, const void *data);
void set_win_tiles(UINT8 x, UINT8 y, UINT8 w, UINT8 h, const void *tiles);
void set_win_tile_xy(UINT8 x, UINT8 y, UINT8 tile);
void get_win_data(UINT8 first, UINT8 count, void *dest);
void get_bkg_data(UINT8 first, UINT8 count, void *dest);
void set_data(void *dest, const void *src, UINT16 size);
void set_vram_byte(void *dest, UINT8 value);
UBYTE get_vram_byte(void *addr);
void fill_bkg_rect(UINT8 x, UINT8 y, UINT8 w, UINT8 h, UINT8 tile);
void fill_win_rect(UINT8 x, UINT8 y, UINT8 w, UINT8 h, UINT8 tile);
void set_sprite_data(UINT8 first, UINT8 count, const void *data);
void set_sprite_tile(UINT8 num, UINT8 tile);
void set_sprite_palette(UINT8 first, UINT8 count, const void *palettes);
void move_sprite(UINT8 num, UINT8 x, UINT8 y);
void hide_sprite(UINT8 num);
void hide_sprites_range(UINT8 from, UINT8 to);
void set_sprite_prop(UINT8 num, UINT8 prop);

/* Some engine headers refer to these GBDK globals. */
extern volatile UBYTE _shadow_OAM_base;
extern volatile UBYTE __render_shadow_OAM;

#endif /* WS_SURVEY_GBDK_PLATFORM_H */
