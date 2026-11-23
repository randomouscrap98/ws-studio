#!/usr/bin/env python3
"""Reference frame for the C15 dialogue-text tests.

Builds the sample-town background with the scene engine's camera rules, then
paints the screen-2 overlay shadow map the way the UI code does:

  SHOW   (1, 1) black, no frame   -> 27x17 black cells
  CLEAR  (0, 0) 20x4 white + frame
  text starts at window cell (1, 1) = screen pixel (16, 16)

Glyph tiles are composed here from the exported variable-width font data
(recode table, width table and 1-bit bitmaps).  The packing rule is documented
in the C15 report: each glyph is shifted into the current 8-pixel tile, and
the overflow (if any) continues at the top of the next tile.  Text is only
wrapped by explicit 0x0a newlines; the compiler emits those.

The C16 "choice" mode adds the UI cursor tile at the menu items' window cells,
and "closed" renders the scene with the overlay window hidden (after
VM_OVERLAY_MOVE_TO y=18).
"""

import argparse
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import boot_oracle  # noqa: E402
import ref_render  # noqa: E402

SCENE = "scene_sample_town"
PLAYER_X = 48              # px, BOOT_START_X = 1536
PLAYER_Y = 80              # px, BOOT_START_Y = 2560
SOURCE_X = 0
SOURCE_Y = 16
WINDOW_X = 8               # tile 1
WINDOW_Y = 8               # tile 1
WINDOW_W = ref_render.WIDTH - WINDOW_X
WINDOW_H = ref_render.HEIGHT - WINDOW_Y
UI_PALETTE = 7

TEXT_BUFFER_START = 0xCC
TEXT_BKG_FILL_W = 0x00
TEXT_BKG_FILL_B = 0xFF

FONT_RECODE = 1
FONT_VWF = 2
FONT_VWF_1BIT = 4

UI_FRAME_TILE = 0xC0
UI_WHITE_TILE = 0xC9
UI_BLACK_TILE = 0xCA
UI_CURSOR_TILE = 0xCB

# ui_a.s _ui_time_masks
TIME_MASKS = (0x00, 0x00, 0x01, 0x03, 0x07, 0x0F, 0x1F, 0x3F)

# The three C15 scripts.  The strings here are the bytes after the compiler's
# .dw/.asciz data has been expanded by vm_load_text.
MODES = {
    "instant": (b"\x01\x01Wow! Found\nGOLD COIN.", ()),
    "speed": (b"\x01\x03Wow! Found\nGOLD COIN.", ()),
    "var": (b"\x01\x01Var: %d and %d.", (-42, 1234)),
    # C16 menu: prompt on row 1, three labels on rows 2-4.  The menu cursor
    # starts on the first item at window cell (1, 2).
    "choice": (b"\x01\x01Pick one:\n1 - One\n2 - Two\n3 - Three", ()),
}

# Cursor cells ("choice" mode), as (window x, window y).
CURSORS = {
    "choice": [(1, 2)],
}

# Modes that render the scene with no overlay window (C16 close tests).
CLOSED_MODES = {"closed"}


def split_top_level(text, sep=","):
    parts, depth, start = [], 0, 0
    for i, ch in enumerate(text):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        elif ch == sep and depth == 0:
            parts.append(text[start:i])
            start = i + 1
    parts.append(text[start:])
    return [p.strip() for p in parts]


class Font:
    def __init__(self, export):
        text = export.text("font_gbs_variable_width")
        match = re.search(
            r"const\s+font_desc_t\s+font_gbs_variable_width\s*=\s*\{(.*?)\};",
            text, re.S)
        if not match:
            raise boot_oracle.OracleError("font descriptor not found")
        fields = split_top_level(match.group(1))
        if len(fields) < 5:
            raise boot_oracle.OracleError("font descriptor is incomplete for font_gbs_variable_width")
        self.attr = 0
        for token in fields[0].split("|"):
            token = token.strip()
            self.attr |= {"FONT_RECODE": FONT_RECODE,
                          "FONT_VWF": FONT_VWF,
                          "FONT_VWF_1BIT": FONT_VWF_1BIT}[token]
        self.mask = int(fields[1], 0)
        self.recode = boot_oracle.ints(
            boot_oracle.array_body(text, fields[2]))
        self.widths = boot_oracle.ints(
            boot_oracle.array_body(text, fields[3]))
        bitmaps = boot_oracle.ints(
            boot_oracle.array_body(text, fields[4]))
        self.bitmaps = [bitmaps[i * 16:(i + 1) * 16]
                        for i in range(len(bitmaps) // 16)]


def make_mask_lr(width, ofs):
    if width == 0:
        return 0xFFFF
    if ofs + width <= 8:
        return (~(((1 << width) - 1) << (8 - ofs - width))) & 0xFF | 0xFF00
    here = 8 - ofs
    rem = width - here
    cur = (0xFF << here) & 0xFF
    nxt = (~(((1 << rem) - 1) << (8 - rem))) & 0xFF
    return cur | (nxt << 8)


def make_mask_rl(width, ofs):
    if width == 0:
        return 0xFFFF
    if ofs + width <= 8:
        return (~(((1 << width) - 1) << ofs)) & 0xFF | 0xFF00
    here = 8 - ofs
    rem = width - here
    cur = ((1 << ofs) - 1) & 0xFF
    nxt = (~((1 << rem) - 1)) & 0xFF
    return cur | (nxt << 8)


def shift_char(dest, base, src, inverse, rotate, mask):
    for row in range(8):
        low = src[row * 2] ^ inverse
        high = src[row * 2 + 1] ^ inverse
        if rotate & 0x80:
            n = rotate & 0x7F
            low = 0 if n >= 8 else (low << n) & 0xFF
            high = 0 if n >= 8 else (high << n) & 0xFF
        else:
            n = rotate
            low = 0 if n >= 8 else low >> n
            high = 0 if n >= 8 else high >> n
        lo_dst = base + row * 2
        dest[lo_dst] = (dest[lo_dst] & mask) | (low & ~mask & 0xFF)
        dest[lo_dst + 1] = (dest[lo_dst + 1] & mask) | (high & ~mask & 0xFF)


def itoa_fmt(value, width):
    out = ""
    if value < 0:
        out = "-"
        if width:
            width -= 1
        value = -value
    digits = str(value)
    if width > len(digits):
        digits = "0" * (width - len(digits)) + digits
    return out + digits


def format_text(fmt, values):
    out = bytearray()
    i = 0
    args = list(values)
    while i < len(fmt):
        ch = fmt[i]
        if ch != 0x25:  # '%'
            out.append(ch)
            i += 1
            continue
        i += 1
        if i >= len(fmt):
            break
        spec = fmt[i]
        if spec == ord("%"):
            out.append(ord("%"))
            i += 1
        elif spec == ord("d"):
            out.extend(itoa_fmt(args.pop(0), 0).encode())
            i += 1
        elif spec == ord("D"):
            out.extend(itoa_fmt(args.pop(0), fmt[i + 1] - 0x30).encode())
            i += 2
        elif spec == ord("c"):
            out.append(args.pop(0) & 0xFF)
            i += 1
        elif spec == ord("t"):
            out.append(0x01)
            out.append((args.pop(0) + 2) & 0xFF)
            i += 1
        elif spec == ord("f"):
            out.append(0x02)
            out.append((args.pop(0) + 1) & 0xFF)
            i += 1
        else:
            out.append(ch)
    return bytes(out)


class TextRenderer:
    """The GB VWF buffer and tile-map writer, independent of engine code."""

    def __init__(self, font, cells, fill=TEXT_BKG_FILL_W):
        self.font = font
        self.cells = cells
        self.fill = fill
        self.direction = 0        # UI_PRINT_LEFTTORIGHT
        self.offset = 0
        self.tile_data = [fill] * 32
        self.current_tile = TEXT_BUFFER_START
        self.current_bank = 0
        self.prev_tile = TEXT_BUFFER_START
        self.prev_bank = 0
        self.dest_base = 32 + 1   # window cell (1, 1)
        self.dest = self.dest_base
        self.tiles = {}

    def upload(self):
        index = self.current_tile + (256 if self.current_bank else 0)
        self.tiles[index] = list(self.tile_data)

    def next_tile(self):
        self.prev_bank = self.current_bank
        self.prev_tile = self.current_tile
        self.current_tile = (self.current_tile + 1) & 0xFF
        if self.current_tile == 0:
            self.current_tile = TEXT_BUFFER_START

    def reset(self):
        if self.offset:
            self.next_tile()
        self.offset = 0
        self.tile_data = [self.fill] * 32

    def set_cell(self, dest, tile, bank):
        index = tile + (256 if bank else 0)
        self.cells[dest % (32 * 32)] = [index, UI_PALETTE, False, False]

    def put_glyph(self, letter):
        width = self.font.widths[letter]
        bitmap = self.font.bitmaps[letter]
        inverse = self.fill if (self.font.attr & FONT_VWF_1BIT) else 0
        if self.direction == 0:
            rotate = self.offset
            masks = make_mask_lr(width, self.offset)
            shift_char(self.tile_data, 0, bitmap, inverse, rotate, masks & 0xFF)
            if (self.offset + width) & 0xFF > 8:
                rotate = (8 - self.offset) | 0x80
                shift_char(self.tile_data, 16, bitmap, inverse, rotate,
                           (masks >> 8) & 0xFF)
        else:
            dx = 8 - self.offset
            rotate = (dx - width) if width < dx else ((width - dx) | 0x80)
            masks = make_mask_rl(width, self.offset)
            shift_char(self.tile_data, 0, bitmap, inverse, rotate, masks & 0xFF)
            if (self.offset + width) & 0xFF > 8:
                rotate = 16 - ((self.offset + width) & 0xFF)
                shift_char(self.tile_data, 16, bitmap, inverse, rotate,
                           (masks >> 8) & 0xFF)
        self.offset += width
        self.upload()
        if self.offset > 7:
            for i in range(16):
                self.tile_data[i] = self.tile_data[i + 16]
            for i in range(16, 32):
                self.tile_data[i] = self.fill
            self.offset -= 8
            self.next_tile()
            if self.offset:
                self.upload()
            return True
        return False


class TextDecoder:
    def __init__(self, font, cells):
        self.font = font
        self.renderer = TextRenderer(font, cells)
        self.pos = 0
        self.drawn = False
        self.speed = 1

    def draw_one(self, data):
        """One call to ui_draw_text_buffer_char()."""
        r = self.renderer
        while self.pos < len(data):
            ch = data[self.pos]
            if ch == 0x00:
                self.drawn = True
                self.pos += 1
                return False
            if ch == 0x01:
                self.speed = (data[self.pos + 1] - 1) & 0x07
                self.pos += 2
                continue
            if ch == 0x02:
                self.pos += 2
                continue
            if ch == 0x03:
                x = data[self.pos + 1]
                y = data[self.pos + 2]
                r.dest = r.dest_base = (x - 1) + (y - 1) * 32
                if r.offset:
                    r.reset()
                self.pos += 3
                continue
            if ch == 0x04:
                dx = data[self.pos + 1] - 1 if data[self.pos + 1] else 0
                dy = data[self.pos + 2] - 1 if data[self.pos + 2] else 0
                r.dest = r.dest_base = (r.dest + dx + dy * 32) & 0xFFFF
                if r.offset:
                    r.reset()
                self.pos += 3
                continue
            if ch == 0x05:
                self.pos += 1
                ch = data[self.pos] if self.pos < len(data) else 0
            if ch == 0x07:
                r.fill = TEXT_BKG_FILL_W if (data[self.pos + 1] & 1) else TEXT_BKG_FILL_B
                self.pos += 2
                continue
            if ch == 0x08:
                r.direction = 0 if (data[self.pos + 1] & 1) else 1
                self.pos += 2
                continue
            if ch == 0x09:
                self.pos += 1
                continue
            if ch == 0x0A:
                r.dest = r.dest_base = (r.dest_base + 32) & 0xFFFF
                if r.offset:
                    r.reset()
                self.pos += 1
                continue
            if ch == 0x0B:
                self.pos += 2
                continue
            if ch == 0x0D:
                self.pos += 1
                continue
            if ch == 0x06:
                # Not used by the C15 scripts; a waiting text consumes the
                # call without drawing.
                self.pos += 2
                return False
            letter = self.font.recode[ch & self.font.mask] \
                if (self.font.attr & FONT_RECODE) else ch
            if r.put_glyph(letter):
                r.set_cell(r.dest, r.prev_tile, r.prev_bank)
                r.dest += 1 if r.direction == 0 else -1
            if r.offset:
                r.set_cell(r.dest, r.current_tile, r.current_bank)
            self.pos += 1
            return True
        self.drawn = True
        return False

    def run(self, data, calls=None):
        if calls is None:
            while not self.drawn:
                self.draw_one(data)
        else:
            for _ in range(calls):
                if self.drawn:
                    break
                self.draw_one(data)
        return self.renderer


def speed_draw_calls(frames):
    """ui_update() calls that pass the ui_time_masks[2] = 1 speed gate.

    The boot scene script first runs on retro frame 24 and the modal text loop
    starts on frame 25; the gate then passes every other frame.
    """
    return max(0, (frames - 23) // 2)


def ui_tiles(export):
    frame = boot_oracle.ints(
        boot_oracle.array_body(export.text("frame_image"), "frame_image"))
    cursor = boot_oracle.ints(
        boot_oracle.array_body(export.text("cursor_image"), "cursor_image"))
    tiles = {}
    for i in range(9):
        tiles[UI_FRAME_TILE + i] = frame[i * 16:(i + 1) * 16]
    tiles[UI_WHITE_TILE] = [0x00] * 16
    tiles[UI_BLACK_TILE] = [0xFF] * 16
    tiles[UI_CURSOR_TILE] = cursor[:16]
    return tiles


def build_window_cells(height=4):
    cells = [[0, 0, False, False] for _ in range(32 * 32)]

    def put(x, y, tile):
        if 0 <= x < 32 and 0 <= y < 32:
            cells[y * 32 + x] = [tile, UI_PALETTE, False, False]

    # VM_OVERLAY_SHOW 1, 1: 27x17 black.
    for y in range(17):
        for x in range(27):
            put(x, y, UI_BLACK_TILE)

    # VM_OVERLAY_CLEAR 0, 0, 20, height with UI_DRAW_FRAME.
    for x in range(20):
        put(x, 0, UI_FRAME_TILE if x == 0 else
            (UI_FRAME_TILE + 2 if x == 19 else UI_FRAME_TILE + 1))
        put(x, height - 1, UI_FRAME_TILE + 6 if x == 0 else
            (UI_FRAME_TILE + 8 if x == 19 else UI_FRAME_TILE + 7))
    for y in range(1, height - 1):
        put(0, y, UI_FRAME_TILE + 3)
        for x in range(1, 19):
            put(x, y, UI_FRAME_TILE + 4)
        put(19, y, UI_FRAME_TILE + 5)
    return cells


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--export", default=str(boot_oracle.DEFAULT_EXPORT))
    parser.add_argument("--project-dir", default=str(boot_oracle.DEFAULT_PROJECT))
    parser.add_argument("--mode", choices=sorted(set(MODES) | CLOSED_MODES),
                        required=True)
    parser.add_argument("--frames", type=int, required=True)
    parser.add_argument("--draw-calls", type=int, default=None,
                        help="override the speed-mode render-call count")
    parser.add_argument("--out", required=True)
    parser.add_argument("--scenario-out", default=None)
    parser.add_argument("--cells-out", default=None,
                        help="write the window cell map as JSON for checking")
    args = parser.parse_args(argv)

    try:
        export = boot_oracle.ExportData(args.export)
        start_dir = boot_oracle.parse_start_dir(args.export)
        final = {
            "source_x": SOURCE_X,
            "source_y": SOURCE_Y,
            "player_x": PLAYER_X,
            "player_y": PLAYER_Y,
        }
        _scene, _bg, _actors, scenario, _expected = boot_oracle.build_scene(
            export, args.project_dir, SCENE, PLAYER_X, PLAYER_Y, start_dir,
            args.frames, effects={}, final=final)

        if args.mode not in CLOSED_MODES:
            font = Font(export)
            fmt, values = MODES[args.mode]
            text = format_text(fmt, values)

            cells = build_window_cells(5 if args.mode == "choice" else 4)
            calls = None
            if args.mode == "speed":
                calls = (args.draw_calls if args.draw_calls is not None
                         else speed_draw_calls(args.frames))
            decoder = TextDecoder(font, cells)
            renderer = decoder.run(text, calls)
            for cx, cy in CURSORS.get(args.mode, []):
                cells[cy * 32 + cx] = [UI_CURSOR_TILE, UI_PALETTE, False, False]

            base_tiles = scenario["bg_tiles"]
            tiles = ui_tiles(export)
            tiles.update(renderer.tiles)
            limit = max(tiles) + 1
            if len(base_tiles) < limit:
                base_tiles.extend([[0] * 16] * (limit - len(base_tiles)))
            for index, data in tiles.items():
                base_tiles[index] = data

            scenario["window"] = {
                "x": WINDOW_X,
                "y": WINDOW_Y,
                "width": WINDOW_W,
                "height": WINDOW_H,
                "scroll_x": (-WINDOW_X) & 0xFF,
                "scroll_y": (-WINDOW_Y) & 0xFF,
                "cells": cells,
            }
            scenario["window_hide_actors"] = True

        if args.scenario_out:
            Path(args.scenario_out).write_text(__import__("json").dumps(scenario))
        if args.cells_out:
            Path(args.cells_out).write_text(__import__("json").dumps(
                {"cells": cells, "tiles": {str(k): v for k, v in tiles.items()},
                 "text": list(text), "calls": calls, "drawn": decoder.drawn}))
        ref_render.render_scenario(scenario, args.out)
    except (boot_oracle.OracleError, OSError, KeyError, ValueError) as exc:
        print("text_oracle: {}".format(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
