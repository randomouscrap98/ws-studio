#!/usr/bin/env python3
"""Reference frame and window position for the C14 overlay test.

The test scene is Sample Town with script_c14_test as its init script.  The
window script in wsc/gamerom/src/script_c14_test.s is:

  SHOW   (1, 0)  black, no frame   -> fills 27x18 window cells
  MOVE   (1, 18) instant           -> hides at the bottom edge
  MOVE   (1, 9) speed 1            -> 1 pixel per game frame
  CLEAR  (0, 0) 27x6 black + frame
  WAIT   non-modal for the window

ui_time_masks[1] is 0, so a speed of 1 moves once every game frame.  Frames
here are counted from the test script's marker.  The window position after K
marker-relative frames is

    y = max(72, 144 - K)

and x is always 8 (tile 1).  The GB hide rule is applied by ref_render.py:
an actor is hidden when its top-left is inside the window and the window is
not at x=0 (WX_REG > 7).
"""

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import boot_oracle  # noqa: E402
import ref_render  # noqa: E402

SCENE = "scene_sample_town"
PLAYER_X = 48              # px, BOOT_START_X = 1536
PLAYER_Y = 80              # px, BOOT_START_Y = 2560
SOURCE_X = 0               # camera source at this small start position
SOURCE_Y = 16
DUCK_INDEX = 3             # scene_sample_town_actors[3] = actor 4
DUCK_X = 96                # px
DUCK_Y = 120               # px, under the window
WINDOW_X = 8               # tile 1
WINDOW_W = 216             # 224 - 8
WINDOW_Y = 72              # tile 9
MOVE_START_Y = 144         # tile 18, closed
UI_PALETTE = 7

FRAME_H = ref_render.HEIGHT

# One pixel is moved per game frame.  Relative to the marker, the first
# moved position is visible at K = 1; the tests stay inside the steady
# one-pixel-per-frame range.
MOVE_FRAME_OFFSET = 144
FIRST_MOVE_FRAME = 1


def window_y_at(frames):
    if frames < FIRST_MOVE_FRAME:
        return MOVE_START_Y
    return max(WINDOW_Y, MOVE_FRAME_OFFSET - frames)


def ui_tiles(export):
    tiles = [[0] * 16 for _ in range(0xCC)]
    frame = boot_oracle.ints(
        boot_oracle.array_body(export.text("frame_image"), "frame_image"))
    cursor = boot_oracle.ints(
        boot_oracle.array_body(export.text("cursor_image"), "cursor_image"))
    tiles[0xC0:0xC0 + 9] = [frame[i * 16:(i + 1) * 16] for i in range(9)]
    tiles[0xC9] = [0x00] * 16
    tiles[0xCA] = [0xFF] * 16
    tiles[0xCB] = cursor[:16]
    return tiles


def build_window_cells():
    cells = [[0, 0, False, False] for _ in range(32 * 32)]

    def put(x, y, tile):
        if 0 <= x < 32 and 0 <= y < 32:
            cells[y * 32 + x] = [tile, UI_PALETTE, False, False]

    # VM_OVERLAY_SHOW 1, 0: clear 27x18 with the black tile.
    for y in range(18):
        for x in range(27):
            put(x, y, 0xCA)

    # VM_OVERLAY_CLEAR 0, 0, 27, 6 with UI_DRAW_FRAME.  Rows 6..8 stay
    # black from the SHOW fill, which exposes the runtime window width when
    # the show loop is broken back to 20 tiles.
    for x in range(27):
        put(x, 0, 0xC0 if x == 0 else (0xC2 if x == 26 else 0xC1))
        put(x, 5, 0xC6 if x == 0 else (0xC8 if x == 26 else 0xC7))
    for y in range(1, 5):
        put(0, y, 0xC3)
        for x in range(1, 26):
            put(x, y, 0xC4)
        put(26, y, 0xC5)
    return cells


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--export", default=str(boot_oracle.DEFAULT_EXPORT))
    parser.add_argument("--project-dir", default=str(boot_oracle.DEFAULT_PROJECT))
    parser.add_argument("--frames", type=int, required=True)
    parser.add_argument("--window-y", type=int, default=None)
    parser.add_argument("--out", required=True)
    parser.add_argument("--scenario-out", default=None)
    args = parser.parse_args(argv)

    try:
        export = boot_oracle.ExportData(args.export)
        start_dir = boot_oracle.parse_start_dir(args.export)
        final = {
            "source_x": SOURCE_X,
            "source_y": SOURCE_Y,
            "player_x": PLAYER_X,
            "player_y": PLAYER_Y,
            "actor_overrides": {
                DUCK_INDEX: {"x": DUCK_X << 5, "y": DUCK_Y << 5},
            },
        }
        _scene, _bg, _actors, scenario, _expected = boot_oracle.build_scene(
            export, args.project_dir, SCENE, PLAYER_X, PLAYER_Y, start_dir,
            args.frames, final=final)

        ui = ui_tiles(export)
        bg_tiles = scenario["bg_tiles"]
        if len(bg_tiles) < len(ui):
            bg_tiles.extend([[0] * 16] * (len(ui) - len(bg_tiles)))
        for index in range(0xC0, 0xCC):
            bg_tiles[index] = ui[index]

        wy = args.window_y if args.window_y is not None else \
            window_y_at(args.frames)
        scenario["window"] = {
            "x": WINDOW_X,
            "y": wy,
            "width": WINDOW_W,
            "height": FRAME_H - wy,
            "scroll_x": (-WINDOW_X) & 0xFF,
            "scroll_y": (-wy) & 0xFF,
            "cells": build_window_cells(),
        }
        scenario["window_hide_actors"] = True

        if args.scenario_out:
            import json
            Path(args.scenario_out).write_text(json.dumps(scenario))
        ref_render.render_scenario(scenario, args.out)
    except (boot_oracle.OracleError, OSError, KeyError, ValueError) as exc:
        print("overlay_oracle: {}".format(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
