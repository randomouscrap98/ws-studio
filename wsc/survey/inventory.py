#!/usr/bin/env python3
"""Inventory GB/GMBK hardware uses in the GBVM engine sources.

Scans the engine .c files (excluding vm.c/vm_dispatch.c, which the C04 tasks
already ported) and counts GBDK calls, Game Boy hardware register names and
SDCC-only constructs.  This is a static count, not a reachability analysis.
"""
import argparse
import re
import sys
from pathlib import Path

SURVEY_DIR = Path(__file__).resolve().parent
WSC_DIR = SURVEY_DIR.parent
ROOT_DIR = WSC_DIR.parent
ENGINE = ROOT_DIR / "appData" / "engine" / "gbvm"

CATEGORIES = [
    "vram_tiles_map",
    "sprites_oam",
    "palettes",
    "scrolling_window",
    "lcd_interrupts_vblank",
    "input",
    "timers",
    "rom_banking",
    "sram_save",
    "sound",
    "serial_printer_sgb",
    "other",
]

# token -> category.  A token may be an engine wrapper around a GBDK call;
# the goal is to find GB-dependent code, not to prove the call is GBDK's.
TOKENS = {
    # VRAM tiles, maps, CGB attribute banks
    "set_bkg_data": "vram_tiles_map",
    "set_bkg_tiles": "vram_tiles_map",
    "set_bkg_submap": "vram_tiles_map",
    "set_bkg_submap_attributes": "vram_tiles_map",
    "set_win_data": "vram_tiles_map",
    "set_win_tiles": "vram_tiles_map",
    "set_win_tile_xy": "vram_tiles_map",
    "set_xy_win_submap": "vram_tiles_map",
    "set_vram_byte": "vram_tiles_map",
    "get_vram_byte": "vram_tiles_map",
    "get_win_data": "vram_tiles_map",
    "get_bkg_data": "vram_tiles_map",
    "set_data": "vram_tiles_map",
    "fill_bkg_rect": "vram_tiles_map",
    "fill_win_rect": "vram_tiles_map",
    "SetBankedBkgData": "vram_tiles_map",
    "SetBankedBkgTiles": "vram_tiles_map",
    "SetBankedWinTiles": "vram_tiles_map",
    "MemcpyVRAMBanked": "vram_tiles_map",
    "VBK_REG": "vram_tiles_map",
    "VBK_BANK_0": "vram_tiles_map",
    "VBK_BANK_1": "vram_tiles_map",
    "VBK_TILES": "vram_tiles_map",
    "VBK_ATTRIBUTES": "vram_tiles_map",
    "GetWinAddr": "vram_tiles_map",
    "GetBkgAddr": "vram_tiles_map",
    "scroll_rect": "vram_tiles_map",

    # Sprites and OAM
    "set_sprite_data": "sprites_oam",
    "set_sprite_tile": "sprites_oam",
    "set_sprite_prop": "sprites_oam",
    "set_sprite_palette": "sprites_oam",
    "SetBankedSpriteData": "sprites_oam",
    "move_metasprite": "sprites_oam",
    "hide_sprites_range": "sprites_oam",
    "SHOW_SPRITES": "sprites_oam",
    "HIDE_SPRITES": "sprites_oam",
    "SPRITES_8x8": "sprites_oam",
    "SPRITES_8x16": "sprites_oam",
    "shadow_OAM": "sprites_oam",
    "shadow_OAM2": "sprites_oam",
    "_shadow_OAM_base": "sprites_oam",
    "__render_shadow_OAM": "sprites_oam",
    "OAM_item_t": "sprites_oam",
    "metasprite_t": "sprites_oam",
    "metasprite_end": "sprites_oam",
    "MAX_HARDWARE_SPRITES": "sprites_oam",
    "toggle_shadow_OAM": "sprites_oam",
    "activate_shadow_OAM": "sprites_oam",

    # Palettes
    "set_bkg_palette": "palettes",
    "set_sprite_palette": "palettes",
    "BGP_REG": "palettes",
    "OBP0_REG": "palettes",
    "OBP1_REG": "palettes",
    "BCPS_REG_ADDR": "palettes",
    "OCPS_REG_ADDR": "palettes",
    "palette_entry_t": "palettes",
    "BkgPalette": "palettes",
    "SprPalette": "palettes",
    "DMG_palette": "palettes",
    "DMG_PALETTE": "palettes",
    "CGB_PALETTE": "palettes",
    "CGB_COLOR": "palettes",
    "CGBZeroPalette": "palettes",
    "CGBFadeToWhiteStep": "palettes",
    "CGBFadeToBlackStep": "palettes",
    "DMGFadeToWhiteStep": "palettes",
    "DMGFadeToBlackStep": "palettes",
    "ApplyPaletteChangeColor": "palettes",
    "ApplyPaletteChangeDMG": "palettes",

    # Scrolling and window
    "SCX_REG": "scrolling_window",
    "SCY_REG": "scrolling_window",
    "WX_REG": "scrolling_window",
    "WY_REG": "scrolling_window",
    "LCDC_REG": "scrolling_window",
    "LCDCF_OFF": "scrolling_window",
    "LCDCF_ON": "scrolling_window",
    "LCDCF_BG8000": "scrolling_window",
    "LCDCF_BG8800": "scrolling_window",
    "LCDCF_BG9800": "scrolling_window",
    "LCDCF_BG9C00": "scrolling_window",
    "LCDCF_WIN9C00": "scrolling_window",
    "LCDCF_WINON": "scrolling_window",
    "LCDCF_OBJ16": "scrolling_window",
    "LCDCF_OBJON": "scrolling_window",
    "LCDCF_BGON": "scrolling_window",
    "SHOW_WIN": "scrolling_window",
    "HIDE_WIN": "scrolling_window",
    "SHOW_BKG": "scrolling_window",
    "HIDE_BKG": "scrolling_window",
    "MAXWNDPOSY": "scrolling_window",
    "DEVICE_WINDOW_PX_OFFSET_X": "scrolling_window",
    "scroll_shadow_update": "scrolling_window",
    "parallax_LCD_isr": "scrolling_window",
    "simple_LCD_isr": "scrolling_window",
    "fullscreen_LCD_isr": "scrolling_window",

    # LCD, interrupts, vblank
    "display_off": "lcd_interrupts_vblank",
    "display_on": "lcd_interrupts_vblank",
    "DISPLAY_ON": "lcd_interrupts_vblank",
    "DISPLAY_OFF": "lcd_interrupts_vblank",
    "add_VBL": "lcd_interrupts_vblank",
    "add_LCD": "lcd_interrupts_vblank",
    "add_TIM": "lcd_interrupts_vblank",
    "add_SIO": "lcd_interrupts_vblank",
    "remove_VBL": "lcd_interrupts_vblank",
    "remove_LCD": "lcd_interrupts_vblank",
    "remove_TIM": "lcd_interrupts_vblank",
    "remove_SIO": "lcd_interrupts_vblank",
    "set_interrupts": "lcd_interrupts_vblank",
    "enable_interrupts": "lcd_interrupts_vblank",
    "disable_interrupts": "lcd_interrupts_vblank",
    "CRITICAL": "lcd_interrupts_vblank",
    "IE_REG": "lcd_interrupts_vblank",
    "IF_REG": "lcd_interrupts_vblank",
    "STAT_REG": "lcd_interrupts_vblank",
    "STATF_LYC": "lcd_interrupts_vblank",
    "STATF_BUSY": "lcd_interrupts_vblank",
    "STATF_B_BUSY": "lcd_interrupts_vblank",
    "LYC_REG": "lcd_interrupts_vblank",
    "LY_REG": "lcd_interrupts_vblank",
    "wait_vbl_done": "lcd_interrupts_vblank",
    "cpu_fast": "lcd_interrupts_vblank",
    "cpu_slow": "lcd_interrupts_vblank",
    "__cpu": "lcd_interrupts_vblank",
    "CGB_TYPE": "lcd_interrupts_vblank",
    "_is_CGB": "lcd_interrupts_vblank",
    "_is_SGB": "lcd_interrupts_vblank",
    "_is_GBA": "lcd_interrupts_vblank",
    "VBL_isr": "lcd_interrupts_vblank",
    "remove_LCD_ISRs": "lcd_interrupts_vblank",
    "LCD_IFLAG": "lcd_interrupts_vblank",
    "TIM_IFLAG": "lcd_interrupts_vblank",
    "SIO_IFLAG": "lcd_interrupts_vblank",
    "VBL_IFLAG": "lcd_interrupts_vblank",

    # Input
    "joypad": "input",
    "joypad_init": "input",
    "joypad_ex": "input",
    "joypads_t": "input",
    "waitpad": "input",
    "waitpadup": "input",
    "J_UP": "input",
    "J_DOWN": "input",
    "J_LEFT": "input",
    "J_RIGHT": "input",
    "J_A": "input",
    "J_B": "input",
    "J_START": "input",
    "J_SELECT": "input",

    # Timers
    "DIV_REG": "timers",
    "TMA_REG": "timers",
    "TAC_REG": "timers",
    "music_setup_timer": "timers",

    # ROM banking and banked-data helpers
    "SWITCH_ROM": "rom_banking",
    "CURRENT_BANK": "rom_banking",
    "BANK": "rom_banking",
    "BANKREF": "rom_banking",
    "BANKREF_EXTERN": "rom_banking",
    "TO_FAR_PTR_T": "rom_banking",
    "far_ptr_t": "rom_banking",
    "ReadBankedFarPtr": "rom_banking",
    "ReadBankedUWORD": "rom_banking",
    "ReadBankedUBYTE": "rom_banking",
    "MemcpyBanked": "rom_banking",
    "IndexOfFarPtr": "rom_banking",
    "__bank_": "rom_banking",
    "__current_bank": "rom_banking",
    "_rROMB0": "rom_banking",

    # SRAM, saves, RTC and flash
    "SWITCH_RAM": "sram_save",
    "SWITCH_RAM_BANK": "sram_save",
    "ENABLE_RAM": "sram_save",
    "DISABLE_RAM": "sram_save",
    "ENABLE_RAM_MBC5": "sram_save",
    "_current_ram_bank": "sram_save",
    "RAM_BANKS_ONLY": "sram_save",
    "RAM_BANKS_AND_FLAGS": "sram_save",
    "SRAM_BANK_SIZE": "sram_save",
    "SRAM_BANKS_TO_SAVE": "sram_save",
    "_start_save": "sram_save",
    "RTC_SELECT_REG": "sram_save",
    "RTC_LATCH_REG": "sram_save",
    "RTC_VALUE_REG": "sram_save",
    "RTC_LATCH": "sram_save",
    "RTC_GET": "sram_save",
    "RTC_SET": "sram_save",
    "RTC_START": "sram_save",
    "save_sram": "sram_save",
    "restore_sram": "sram_save",
    "restore_sram_bank": "sram_save",
    "erase_flash": "sram_save",

    # Sound
    "NR10_REG": "sound",
    "NR11_REG": "sound",
    "NR12_REG": "sound",
    "NR13_REG": "sound",
    "NR14_REG": "sound",
    "NR21_REG": "sound",
    "NR22_REG": "sound",
    "NR23_REG": "sound",
    "NR24_REG": "sound",
    "NR30_REG": "sound",
    "NR31_REG": "sound",
    "NR32_REG": "sound",
    "NR33_REG": "sound",
    "NR34_REG": "sound",
    "NR41_REG": "sound",
    "NR42_REG": "sound",
    "NR43_REG": "sound",
    "NR44_REG": "sound",
    "NR50_REG": "sound",
    "NR51_REG": "sound",
    "NR52_REG": "sound",
    "__AUD3WAVERAM": "sound",
    "music_init": "sound",
    "music_init_driver": "sound",
    "music_init_events": "sound",
    "music_load": "sound",
    "music_stop": "sound",
    "music_pause": "sound",
    "music_setpos": "sound",
    "music_play_isr": "sound",
    "music_events_update": "sound",
    "music_events_poll": "sound",
    "music_play_sfx": "sound",
    "music_sound_cut": "sound",
    "music_sound_cut_mask": "sound",
    "sfx_play_isr": "sound",
    "sfx_sound_init": "sound",
    "sfx_sound_cut": "sound",
    "sfx_sound_cut_mask": "sound",
    "sfx_set_sample": "sound",
    "driver_init": "sound",
    "driver_update": "sound",
    "driver_set_mute_mask": "sound",
    "driver_reset_wave": "sound",
    "hUGE_init": "sound",
    "hUGE_dosound": "sound",
    "hUGE_mute_mask": "sound",
    "hUGE_set_position": "sound",
    "hUGE_reset_wave": "sound",
    "hUGETrackerRoutine": "sound",
    "gbt_play": "sound",
    "gbt_update": "sound",
    "gbt_loop": "sound",
    "gbt_enable_channels": "sound",
    "gbt_reset_ch3_instrument": "sound",
    "TRACK_T": "sound",
    "MUTE_MASK_NONE": "sound",
    "MUTE_MASK_WAVE": "sound",
    "MUSIC_STOP_BANK": "sound",
    "MUSIC_SFX_PRIORITY_MINIMAL": "sound",
    "MUSIC_SFX_PRIORITY_NORMAL": "sound",
    "MUSIC_SFX_PRIORITY_HIGH": "sound",
    "SFX_STOP_BANK": "sound",
    "SFX_CH_RETRIGGER": "sound",
    "SFX_CH_ENABLE": "sound",
    "SFX_MUTE_MASK": "sound",

    # Serial, printer, SGB
    "SB_REG": "serial_printer_sgb",
    "SC_REG": "serial_printer_sgb",
    "SIO_init": "serial_printer_sgb",
    "SIO_send_byte": "serial_printer_sgb",
    "SIO_send_async": "serial_printer_sgb",
    "SIO_receive": "serial_printer_sgb",
    "SIO_set_mode": "serial_printer_sgb",
    "SIO_update": "serial_printer_sgb",
    "IO_IDLE": "serial_printer_sgb",
    "IO_SENDING": "serial_printer_sgb",
    "IO_RECEIVING": "serial_printer_sgb",
    "IO_ERROR": "serial_printer_sgb",
    "LINK_MODE_NONE": "serial_printer_sgb",
    "LINK_MODE_MASTER": "serial_printer_sgb",
    "LINK_MODE_SLAVE": "serial_printer_sgb",
    "sgb_transfer": "serial_printer_sgb",
    "sgb_check": "serial_printer_sgb",
    "set_sgb_border": "serial_printer_sgb",
    "SGBTransferPalettes": "serial_printer_sgb",
    "SGB_TRANSFER": "serial_printer_sgb",
    "SGB_CHR_TRN": "serial_printer_sgb",
    "gbprinter_detect": "serial_printer_sgb",
    "gbprinter_print_overlay": "serial_printer_sgb",
    "printer_init": "serial_printer_sgb",
    "printer_send_receive": "serial_printer_sgb",
    "printer_send_byte": "serial_printer_sgb",
    "printer_send_command": "serial_printer_sgb",
    "printer_print_tile": "serial_printer_sgb",
    "printer_wait": "serial_printer_sgb",
    "PRN_MAGIC": "serial_printer_sgb",
    "PRN_LE": "serial_printer_sgb",
    "PRN_CMD_INIT": "serial_printer_sgb",
    "PRN_CMD_PRINT": "serial_printer_sgb",
    "PRN_CMD_DATA": "serial_printer_sgb",
    "PRN_CMD_BREAK": "serial_printer_sgb",
    "PRN_CMD_STATUS": "serial_printer_sgb",
    "PRN_STATUS_BUSY": "serial_printer_sgb",
    "PRN_STATUS_OK": "serial_printer_sgb",
    "PRN_STATUS_MASK_ERRORS": "serial_printer_sgb",
    "PRN_STATUS_MASK_ANY": "serial_printer_sgb",
    "PRN_PKT_INIT": "serial_printer_sgb",
    "PRN_PKT_STATUS": "serial_printer_sgb",
    "PRN_PKT_EOF": "serial_printer_sgb",
    "PRN_PKT_CANCEL": "serial_printer_sgb",
    "PRN_PKT_START": "serial_printer_sgb",
    "PRINTER_SEND_COMMAND": "serial_printer_sgb",

    # Other libc / GBDK helpers
    "memcpy": "other",
    "memset": "other",
    "memmove": "other",
    "strlen": "other",
    "strcmp": "other",
    "abs": "other",
    "rand": "other",
    "initrand": "other",
    "randw": "other",
    "arand": "other",
    "isqrt": "other",
    "atan2": "other",
    "delay": "other",
}

SDCC_TOKENS = [
    "__asm",
    "__endasm",
    "__naked",
    "__at",
    "__sfr",
    "__preserves_regs",
    "__sdcccall",
    "pragma bank",
    "BANKED",
    "NONBANKED",
    "NAKED",
    "OLDCALL",
    "PRESERVES_REGS",
    "FASTUBYTE",
]

WORD_RE = {token: re.compile(r"(?<![A-Za-z0-9_])" + re.escape(token) + r"(?![A-Za-z0-9_])")
           for token in TOKENS}
SDCC_RE = {token: re.compile(r"(?<![A-Za-z0-9_])" + re.escape(token) + r"(?![A-Za-z0-9_])")
           for token in SDCC_TOKENS}


def sources():
    files = [ENGINE / "src" / "main.c"]
    files += sorted((ENGINE / "src" / "core").glob("*.c"))
    files += sorted((ENGINE / "src" / "states").glob("*.c"))
    return [path for path in files if path.name not in ("vm.c", "vm_dispatch.c")]


def scan(path):
    text = path.read_text(encoding="utf-8", errors="replace")
    # Ignore the #pragma token spelling difference.
    text = text.replace("#pragma bank", "pragma bank")
    counts = {}
    for token, regex in WORD_RE.items():
        found = len(regex.findall(text))
        if found:
            counts[token] = found
    sdcc = {}
    for token, regex in SDCC_RE.items():
        found = len(regex.findall(text))
        if found:
            sdcc[token] = found
    return text.count("\n") + 1, counts, sdcc


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tsv", type=Path,
                        default=WSC_DIR / "build" / "survey" / "inventory.tsv")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    rows = []
    for path in sources():
        rel = path.relative_to(ROOT_DIR)
        lines, counts, sdcc = scan(path)
        per_cat = {cat: 0 for cat in CATEGORIES}
        names = {cat: [] for cat in CATEGORIES}
        for token, found in sorted(counts.items()):
            cat = TOKENS[token]
            per_cat[cat] += found
            names[cat].append("{}({})".format(token, found))
        total = sum(per_cat.values())
        sdcc_total = sum(sdcc.values())
        rows.append((str(rel), lines, total, per_cat, names, sdcc, sdcc_total))

    if not args.quiet:
        header = ["file", "lines", "GB"] + [c[:8] for c in CATEGORIES] + ["SDCC"]
        print("{:<44} {:>5} {:>4} ".format("file", "lines", "GB")
              + " ".join("{:>8}".format(c[:8]) for c in CATEGORIES)
              + " {:>4}".format("SDCC"))
        for rel, lines, total, per_cat, _names, _sdcc, sdcc_total in rows:
            print("{:<44} {:>5} {:>4} ".format(rel, lines, total)
                  + " ".join("{:>4}".format(per_cat[c]) for c in CATEGORIES)
                  + " {:>4}".format(sdcc_total))

    args.tsv.parent.mkdir(parents=True, exist_ok=True)
    with args.tsv.open("w", encoding="utf-8", newline="") as handle:
        handle.write("file\tlines\ttotal\t" + "\t".join(CATEGORIES)
                     + "\tsdcc\t" + "\t".join(c + "_names" for c in CATEGORIES)
                     + "\tsdcc_names\n")
        for rel, lines, total, per_cat, names, sdcc, sdcc_total in rows:
            handle.write("{}\t{}\t{}\t".format(rel, lines, total))
            handle.write("\t".join(str(per_cat[c]) for c in CATEGORIES))
            handle.write("\t{}\t".format(sdcc_total))
            handle.write("\t".join(",".join(names[c]) for c in CATEGORIES))
            handle.write("\t" + ",".join(
                "{}({})".format(token, sdcc[token]) for token in sorted(sdcc)) + "\n")
    if not args.quiet:
        print("\nwrote {}".format(args.tsv))
    return 0


if __name__ == "__main__":
    sys.exit(main())
