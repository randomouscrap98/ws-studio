#!/usr/bin/env python3
"""Reference frames for the C18 tile-map tests.

Two modes:

big   -- the generated 16x18 background with 264 bank-0 tiles, a 4-tile
         cgb_tileset and attribute-bit-3 cells.  The renderer has its own
         copy of the WSC layout (BG bank 1 at 512, blank at 1023); it does
         not import engine constants.
blank -- the exported logo background (20x18, centred) with a long dialogue
         that loads text tile 0xFF.  The 32-px border on each side must stay
         blank.

Both hand a WSC hardware scenario to ref_render.py.
"""

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import boot_oracle  # noqa: E402
import ref_render  # noqa: E402
import text_oracle  # noqa: E402

# This renderer's own copy of the WSC tile layout.  Keep it independent from
# the engine's wsc_tiles.h.
BG_BANK1_BASE = 512
BLANK_TILE = 1023

DATA_JSON = boot_oracle.WSC / "build" / "gamerom" / "c18" / "c18_bg_data.json"

BLANK_TEXT = (
    b"\x01\x01"
    b"ABCDEFGHIJK\nLMNOPQRSTUV\nWXYZabcdefg\nhijklmnopqr\n"
    b"stuvwxyz012\n3456789 !?.\n,:;'-()+/=<\n>ABCDEFGHIJ"
)

WINDOW_X = 8 * 8          # tiles -> pixels
WINDOW_Y = 4 * 8
WINDOW_W = 13
WINDOW_H = 10
UI_PALETTE = 7

UI_FRAME_TILE = 0xC0
UI_WHITE_TILE = 0xC9
UI_BLACK_TILE = 0xCA


def load_big_data(path):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError) as exc:
        raise boot_oracle.OracleError(
            "cannot read {}: {}".format(path, exc)) from exc


def big_scenario(data):
    screen_w = ref_render.WIDTH
    screen_h = ref_render.HEIGHT
    image_w = data["width"] * 8
    image_h = data["height"] * 8

    # Final tile store contents: the bank-0 tileset, the cgb tiles at
    # bank-1 0..3, and the overflow tiles at bank-1 4..7 (the cgb load runs
    # last and covers the first 4 overflow slots).
    tiles = [[0] * 16 for _ in range(BG_BANK1_BASE + data["overflow_tiles"] + 256)]
    for i, tile in enumerate(data["tileset"]):
        tiles[i] = tile
    for i, tile in enumerate(data["cgb_tileset"]):
        tiles[BG_BANK1_BASE + i] = tile
    # The overflow load writes all 8 tiles at bank-1 0..7, then the cgb
    # load replaces the first len(cgb_tileset) slots.
    overflow = data["tileset"][256:]
    for index in range(len(data["cgb_tileset"]), len(overflow)):
        tiles[BG_BANK1_BASE + index] = overflow[index]

    cells = [[BLANK_TILE, 0, False, False] for _ in range(32 * 32)]
    for y in range(data["height"]):
        for x in range(data["width"]):
            off = y * data["width"] + x
            tile = data["tilemap"][off]
            attr = data["attrs"][off]
            index = BG_BANK1_BASE + tile if attr & 0x08 else tile
            cells[y * 32 + x] = [
                index, attr & 0x07, bool(attr & 0x20), bool(attr & 0x40)
            ]

    center_x = (screen_w - image_w) // 2
    center_y = (screen_h - image_h) // 2
    return {
        "width": screen_w,
        "height": screen_h,
        "scroll_x": (-center_x) & 0xFF,
        "scroll_y": (-center_y) & 0xFF,
        "screen": cells,
        "bg_tiles": tiles,
        "bg_palettes": data["palette"],
        "sprites": [],
    }


def put(cells, x, y, tile):
    if 0 <= x < 32 and 0 <= y < 32:
        cells[y * 32 + x] = [tile, UI_PALETTE, False, False]


def draw_frame(cells, x, y, w, h):
    put(cells, x, y, UI_FRAME_TILE)
    for i in range(1, w - 1):
        put(cells, x + i, y, UI_FRAME_TILE + 1)
    put(cells, x + w - 1, y, UI_FRAME_TILE + 2)
    if h == 1:
        return
    for row in range(1, h - 1):
        put(cells, x, y + row, UI_FRAME_TILE + 3)
        for col in range(1, w - 1):
            put(cells, x + col, y + row, UI_FRAME_TILE + 4)
        put(cells, x + w - 1, y + row, UI_FRAME_TILE + 5)
    put(cells, x, y + h - 1, UI_FRAME_TILE + 6)
    for i in range(1, w - 1):
        put(cells, x + i, y + h - 1, UI_FRAME_TILE + 7)
    put(cells, x + w - 1, y + h - 1, UI_FRAME_TILE + 8)


def window_cells():
    cells = [[0, 0, False, False] for _ in range(32 * 32)]
    # VM_OVERLAY_SHOW 8, 4 fills the rest of the screen with black.
    show_w = (ref_render.WIDTH // 8) - WINDOW_X // 8
    show_h = (ref_render.HEIGHT // 8) - WINDOW_Y // 8
    for y in range(show_h):
        for x in range(show_w):
            put(cells, x, y, UI_BLACK_TILE)
    draw_frame(cells, 0, 0, WINDOW_W, WINDOW_H)
    return cells


def blank_scenario(export, project, start_dir):
    _scene, _bg, _actors, scenario, _expected = boot_oracle.build_scene(
        export, project, "scene_logo", 0, 0, start_dir, 200,
        effects={"hide_player": True}, final={"source_x": 0, "source_y": 0})

    font = text_oracle.Font(export)
    cells = window_cells()
    decoder = text_oracle.TextDecoder(font, cells)
    renderer = decoder.run(BLANK_TEXT)
    if not decoder.drawn:
        raise boot_oracle.OracleError("blank-border text did not finish")

    tiles = text_oracle.ui_tiles(export)
    tiles.update(renderer.tiles)
    limit = max(tiles) + 1
    base_tiles = scenario["bg_tiles"]
    if len(base_tiles) < limit:
        base_tiles.extend([[0] * 16] * (limit - len(base_tiles)))
    for index, data in tiles.items():
        base_tiles[index] = data

    scenario["window"] = {
        "x": WINDOW_X,
        "y": WINDOW_Y,
        "width": ref_render.WIDTH - WINDOW_X,
        "height": ref_render.HEIGHT - WINDOW_Y,
        "scroll_x": (-WINDOW_X) & 0xFF,
        "scroll_y": (-WINDOW_Y) & 0xFF,
        "cells": cells,
    }
    scenario["window_hide_actors"] = False
    return scenario


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--mode", choices=("big", "blank"), required=True)
    parser.add_argument("--data", default=str(DATA_JSON))
    parser.add_argument("--export", default=str(boot_oracle.DEFAULT_EXPORT))
    parser.add_argument("--project-dir", default=str(boot_oracle.DEFAULT_PROJECT))
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)

    try:
        if args.mode == "big":
            scenario = big_scenario(load_big_data(args.data))
        else:
            export = boot_oracle.ExportData(args.export)
            start_dir = boot_oracle.parse_start_dir(args.export)
            scenario = blank_scenario(export, args.project_dir, start_dir)
        ref_render.render_scenario(scenario, args.out)
    except (boot_oracle.OracleError, OSError, KeyError, ValueError) as exc:
        print("c18_oracle: {}".format(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
