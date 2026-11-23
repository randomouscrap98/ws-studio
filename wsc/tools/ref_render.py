#!/usr/bin/env python3
"""Render the expected C05/C06 frame from the ROM's GB-format data.

The data arrays are parsed from the hand-written C sources so the ROM and this
renderer share one source of truth.  The output is the 224x144 RGB24 frame as
wsrun emits it: WSC RGB444 colours expanded exactly as beetle-wswan's
RGB565 output plus wsrun's RGB565->RGB24 conversion, i.e. nibble*17 truncated
to 5/6 bits and then bit-replicated.  That makes an exact byte comparison
valid for the pinned emulator.

Sprites are composited with the WSC rules the core implements: index 0 is
transparent, the sprite table is drawn from the highest index down (so lower
indices win sprite-to-sprite overlaps), and screen 1 has no priority bit, so
sprites always cover the background.
"""
import argparse
import re
import sys
from pathlib import Path

WIDTH = 224
HEIGHT = 144
TILE = 8

MODE_8X8 = 0
MODE_8X16 = 1
FLIP_H = 1
FLIP_V = 2


def parse_arrays(path):
    text = path.read_text(encoding="utf-8")
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    text = re.sub(r"//[^\n]*", "", text)
    arrays = {}
    for match in re.finditer(r"\b(\w+)\s*\[\s*\]\s*=\s*\{(.*?)\}\s*;",
                             text, re.S):
        name = match.group(1)
        body = match.group(2)
        arrays[name] = [int(token, 0) for token in
                        re.findall(r"0[xX][0-9a-fA-F]+|\d+", body)]
    return arrays


def parse_metasprite(path, name):
    text = path.read_text(encoding="utf-8")
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    text = re.sub(r"//[^\n]*", "", text)
    match = re.search(r"\b" + re.escape(name) + r"\s*\[\s*\]\s*=\s*\{(.*?)\}\s*;",
                      text, re.S)
    if match is None:
        raise ValueError("metasprite {} not found".format(name))
    return [
        (int(dy, 0), int(dx, 0), int(dtile, 0), int(props, 0))
        for dy, dx, dtile, props in re.findall(
            r"\{\s*(-?\d+)\s*,\s*(-?\d+)\s*,\s*(-?\d+)\s*,\s*"
            r"(0[xX][0-9a-fA-F]+|\d+)\s*\}", match.group(1))
    ]


def parse_defines(path):
    text = path.read_text(encoding="utf-8")
    values = {}
    for match in re.finditer(
            r"^\s*#define\s+(\w+)\s+(0[xX][0-9a-fA-F]+|\d+)\s*$",
            text, re.M):
        values[match.group(1)] = int(match.group(2), 0)
    return values


def expand4(value, green):
    """Expand a WSC RGB444 nibble through RGB565 to the 8-bit wsrun output."""
    wide = value * 17
    if green:
        q = wide >> 2
        return (q << 2) | (q >> 4)
    q = wide >> 3
    return (q << 3) | (q >> 2)


def convert_palette(cgb):
    r = (cgb & 0x1F) >> 1
    g = ((cgb >> 5) & 0x1F) >> 1
    b = ((cgb >> 10) & 0x1F) >> 1
    return (expand4(r, False), expand4(g, True), expand4(b, False))


def render_bg(arrays, scroll, out):
    tiles = [arrays["bg_tiles"], arrays["bg_tiles_hi"]]
    map_data = arrays["bg_map"]
    attrs = arrays["bg_attrs"]
    cgb_palettes = arrays["bg_palettes"]

    palettes = []
    for p in range(len(cgb_palettes) // 4):
        # Entry 0 is cleared by hal_set_bkg_palette; entries 1-4 convert.
        palettes.append([(0, 0, 0)] + [
            convert_palette(cgb_palettes[p * 4 + i]) for i in range(4)
        ])

    def pixel(tile_index, row, col):
        bank = tile_index >> 8
        number = tile_index & 0xFF
        data = tiles[bank] if bank < len(tiles) else []
        if (number + 1) * 16 > len(data):
            return 0
        base = number * 16 + row * 2
        low = data[base]
        high = data[base + 1]
        bit = 7 - col
        return ((low >> bit) & 1) | (((high >> bit) & 1) << 1)

    pos = 0
    for y in range(HEIGHT):
        map_row = (y >> 3) & 31
        for x in range(WIDTH):
            px = x + scroll
            map_col = (px >> 3) & 31
            off = map_row * 32 + map_col
            attr = attrs[off]
            index = map_data[off] | (0x100 if attr & 0x08 else 0)

            tx = px & 7
            ty = y & 7
            if attr & 0x20:
                tx = 7 - tx
            if attr & 0x40:
                ty = 7 - ty

            wsc_index = pixel(index, ty, tx) + 1
            palette = attr & 0x07
            if palette >= len(palettes):
                colour = (0, 0, 0)
            else:
                colour = palettes[palette][wsc_index]
            out[pos:pos + 3] = bytes(colour)
            pos += 3


def metasprite_sprites(entries, base_tile, props, x, y, mode, flip):
    sprites = []
    cur_x, cur_y = x, y

    for dy, dx, dtile, entry_props in entries:
        p = props | entry_props
        flip_h = bool(flip & FLIP_H) ^ bool(p & 0x20)
        flip_v = bool(flip & FLIP_V) ^ bool(p & 0x40)

        if flip & FLIP_H:
            dx = -dx
        if flip & FLIP_V:
            dy = -dy
        cur_x += dx
        cur_y += dy

        tile = (base_tile + dtile) & 0xFF
        if p & 0x08:
            tile += 256
        palette = p & 0x07

        if mode == MODE_8X16:
            top = tile & 0xFE
            if flip_v:
                # V-flip swaps the halves as well as flipping them.
                sprites.append((top | 1, cur_x, cur_y, flip_h, flip_v,
                                palette))
                sprites.append((top, cur_x, cur_y + 8, flip_h, flip_v,
                                palette))
            else:
                sprites.append((top, cur_x, cur_y, flip_h, flip_v, palette))
                sprites.append((top | 1, cur_x, cur_y + 8, flip_h, flip_v,
                                palette))
        else:
            sprites.append((tile, cur_x, cur_y, flip_h, flip_v, palette))

    return sprites


def hardware_sprite_position(x, y, width, height):
    """Model the HAL cull and the WSC 8-bit sprite coordinates.

    The HAL drops an 8x8 entry whose signed position is completely outside
    the 224x144 runtime screen.  Entries that are only partly off the
    left/top edge are kept; writing the low byte makes x = -4 into 252, and
    beetle-wswan treats x >= 249 (and y > 150) as a negative 8-bit value.
    """
    x = int(x)
    y = int(y)
    if x >= width or x + TILE <= 0 or y >= height or y + TILE <= 0:
        return None
    hx = x & 0xFF
    if hx >= 249:
        hx -= 256
    hy = y & 0xFF
    if hy > 150:
        hy = (hy ^ 0x80) - 0x80
    return hx, hy


def render_sprites(out, sprite_data, tile_first, sprites):
    tiles = sprite_data["spr_tiles"]
    cgb_palettes = sprite_data["spr_palettes"]
    palettes = [
        [convert_palette(cgb_palettes[p * 4 + i]) for i in range(4)]
        for p in range(len(cgb_palettes) // 4)
    ]

    def pixel(tile, row, col):
        index = tile - tile_first
        if index < 0 or (index + 1) * 16 > len(tiles):
            return 0
        base = index * 16 + row * 2
        low = tiles[base]
        high = tiles[base + 1]
        bit = 7 - col
        return ((low >> bit) & 1) | (((high >> bit) & 1) << 1)

    visible = []
    for tile, x, y, flip_h, flip_v, palette in sprites:
        position = hardware_sprite_position(x, y, WIDTH, HEIGHT)
        if position is None:
            continue
        visible.append((tile, position[0], position[1], flip_h, flip_v,
                        palette))

    # Match the core: draw high table indices first, so lower indices win.
    for tile, x, y, flip_h, flip_v, palette in reversed(visible):
        for row in range(8):
            ty = 7 - row if flip_v else row
            py = y + row
            if py < 0 or py >= HEIGHT:
                continue
            for col in range(8):
                tx = 7 - col if flip_h else col
                index = pixel(tile, ty, tx)
                if index == 0:
                    continue
                px = x + col
                if px < 0 or px >= WIDTH:
                    continue
                colour = palettes[palette][index]
                pos = (py * WIDTH + px) * 3
                out[pos:pos + 3] = bytes(colour)



def render_scenario(scenario, out_path):
    """Render a scenario produced by boot_oracle.py.

    The scenario already describes the WSC screen-1 cell map (32x32), the
    background tile data and final 8x8 sprite entries, so this follows the
    hardware rather than the engine's loaders.
    """
    width = int(scenario.get("width", WIDTH))
    height = int(scenario.get("height", HEIGHT))
    bg_tiles = scenario["bg_tiles"]
    bg_palettes = scenario["bg_palettes"]
    cells = scenario["screen"]
    spr_tiles = scenario.get("spr_tiles", [])
    sprites = scenario.get("sprites", [])
    scroll_x = int(scenario.get("scroll_x", 0)) & 0xFF
    scroll_y = int(scenario.get("scroll_y", 0)) & 0xFF

    palettes = [ [(0, 0, 0)] + [
        convert_palette(c) for c in bg_palettes[p * 4:p * 4 + 4]
    ] for p in range(len(bg_palettes) // 4) ]

    out = bytearray(width * height * 3)
    pos = 0
    for y in range(height):
        map_row = ((y + scroll_y) >> 3) & 31
        for x in range(width):
            map_col = ((x + scroll_x) >> 3) & 31
            tile, palette, flip_h, flip_v = cells[map_row * 32 + map_col]
            data = bg_tiles[tile] if tile < len(bg_tiles) else None
            index = 0
            if data is not None:
                tx = x & 7
                ty = y & 7
                if flip_h:
                    tx = 7 - tx
                if flip_v:
                    ty = 7 - ty
                base = ty * 2
                bit = 7 - tx
                index = ((data[base] >> bit) & 1) | (
                    ((data[base + 1] >> bit) & 1) << 1)
            if palette < len(palettes):
                colour = palettes[palette][index + 1]
            else:
                colour = (0, 0, 0)
            out[pos:pos + 3] = bytes(colour)
            pos += 3

    window = scenario.get("window")
    if window:
        wx = int(window.get("x", 0))
        wy = int(window.get("y", 0))
        ww = int(window.get("width", width - wx))
        wh = int(window.get("height", height - wy))
        wscroll_x = int(window.get("scroll_x", 0)) & 0xFF
        wscroll_y = int(window.get("scroll_y", 0)) & 0xFF
        wcells = window["cells"]
        for py in range(max(0, wy), min(height, wy + wh)):
            sy = (py + wscroll_y) & 0xFF
            for px in range(max(0, wx), min(width, wx + ww)):
                sx = (px + wscroll_x) & 0xFF
                tile, palette, flip_h, flip_v = wcells[
                    ((sy >> 3) & 31) * 32 + ((sx >> 3) & 31)]
                data = bg_tiles[tile] if tile < len(bg_tiles) else None
                index = 0
                if data is not None:
                    tx = sx & 7
                    ty = sy & 7
                    if flip_h:
                        tx = 7 - tx
                    if flip_v:
                        ty = 7 - ty
                    base = ty * 2
                    bit = 7 - tx
                    index = ((data[base] >> bit) & 1) | (
                        ((data[base + 1] >> bit) & 1) << 1)
                if palette < len(palettes):
                    colour = palettes[palette][index + 1]
                else:
                    colour = (0, 0, 0)
                offset = (py * width + px) * 3
                out[offset:offset + 3] = bytes(colour)

    # GB Studio hides an actor whose top-left is inside the window when the
    # window is shown away from the left edge.  The WSC HAL puts sprites in
    # front of screen 2, so the reference has to apply the same rule.
    if window and scenario.get("window_hide_actors", True):
        wx = int(window.get("x", 0))
        wy = int(window.get("y", 0))
        hidden = set()
        if wx < width and wy < height:
            for gx, gy, first, count in scenario.get("sprite_groups", []):
                if (gx + 8 > wx + 7) and (gy - 8 > wy):
                    hidden.update(range(first, first + count))
        if hidden:
            sprites = [sprite for index, sprite in enumerate(sprites)
                       if index not in hidden]

    sprite_palettes = [
        [convert_palette(c) for c in scenario.get("spr_palettes", [])[p * 4:p * 4 + 4]]
        for p in range(len(scenario.get("spr_palettes", [])) // 4)
    ]

    def sprite_pixel(tile, row, col):
        index = tile - 256
        if index < 0 or index >= len(spr_tiles):
            return 0
        data = spr_tiles[index]
        base = row * 2
        bit = 7 - col
        return ((data[base] >> bit) & 1) | (((data[base + 1] >> bit) & 1) << 1)

    visible = []
    for sprite in sprites:
        tile, x, y, flip_h, flip_v, palette = sprite
        position = hardware_sprite_position(x, y, width, height)
        if position is None:
            continue
        visible.append((tile, position[0], position[1], flip_h, flip_v,
                        palette))

    for tile, x, y, flip_h, flip_v, palette in reversed(visible):
        for row in range(8):
            ty = 7 - row if flip_v else row
            py = y + row
            if py < 0 or py >= height:
                continue
            for col in range(8):
                tx = 7 - col if flip_h else col
                index = sprite_pixel(tile, ty, tx)
                if index == 0:
                    continue
                px = x + col
                if px < 0 or px >= width:
                    continue
                if palette < len(sprite_palettes):
                    colour = sprite_palettes[palette][index]
                else:
                    colour = (0, 0, 0)
                pos = (py * width + px) * 3
                out[pos:pos + 3] = bytes(colour)

    Path(out_path).write_bytes(out)


def main():
    base_data = Path(__file__).resolve().parent.parent / "halrom" / "src"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", default=str(base_data / "bg_data.c"),
                        help="bg_data.c to read")
    parser.add_argument("--sprite-data", default=str(base_data / "spr_data.c"),
                        help="spr_data.c to read")
    parser.add_argument("--sprite-header", default=str(base_data / "spr_data.h"),
                        help="spr_data.h with tile bases and start positions")
    parser.add_argument("--scroll", type=int, default=0,
                        help="horizontal scroll in pixels")
    parser.add_argument("--player-x", type=int, default=None,
                        help="player metasprite x (default: PLAYER_START_X)")
    parser.add_argument("--player-y", type=int, default=None,
                        help="player metasprite y (default: PLAYER_START_Y)")
    parser.add_argument("--accent-x", type=int, default=None,
                        help="8x8 flip demo x (default: ACCENT_X)")
    parser.add_argument("--accent-y", type=int, default=None,
                        help="8x8 flip demo y (default: ACCENT_Y)")
    parser.add_argument("--scenario", default=None,
                        help="JSON scenario from boot_oracle.py")
    parser.add_argument("--out", required=True, help="output RGB24 file")
    args = parser.parse_args()

    if args.scenario is not None:
        import json
        try:
            scenario = json.loads(Path(args.scenario).read_text())
        except (OSError, ValueError) as exc:
            print("ref_render: cannot read scenario: {}".format(exc), file=sys.stderr)
            return 2
        try:
            render_scenario(scenario, args.out)
        except (KeyError, TypeError, ValueError) as exc:
            print("ref_render: invalid scenario: {}".format(exc), file=sys.stderr)
            return 2
        return 0

    try:
        arrays = parse_arrays(Path(args.data))
        sprite_data = parse_arrays(Path(args.sprite_data))
        defines = parse_defines(Path(args.sprite_header))
        player_meta = parse_metasprite(Path(args.sprite_data),
                                       "spr_player_metasprite")
        accent_meta = parse_metasprite(Path(args.sprite_data),
                                       "spr_accent_metasprite")
    except OSError as exc:
        print("ref_render: cannot read data: {}".format(exc), file=sys.stderr)
        return 2
    except ValueError as exc:
        print("ref_render: {}".format(exc), file=sys.stderr)
        return 2

    required = ("bg_tiles", "bg_tiles_hi", "bg_palettes", "bg_map", "bg_attrs")
    missing = [name for name in required if name not in arrays]
    missing += [name for name in ("spr_tiles", "spr_palettes")
                if name not in sprite_data]
    missing += [name for name in
                ("SPR_PLAYER_BASE", "SPR_ACCENT_BASE", "SPR_TILE_FIRST",
                 "PLAYER_START_X", "PLAYER_START_Y", "ACCENT_X", "ACCENT_Y")
                if name not in defines]
    if missing:
        print("ref_render: missing data: {}".format(", ".join(missing)),
              file=sys.stderr)
        return 2

    player_x = args.player_x
    if player_x is None:
        player_x = defines["PLAYER_START_X"]
    player_y = args.player_y
    if player_y is None:
        player_y = defines["PLAYER_START_Y"]
    accent_x = args.accent_x
    if accent_x is None:
        accent_x = defines["ACCENT_X"]
    accent_y = args.accent_y
    if accent_y is None:
        accent_y = defines["ACCENT_Y"]

    frame = bytearray(WIDTH * HEIGHT * 3)
    render_bg(arrays, args.scroll, frame)

    sprites = metasprite_sprites(
        player_meta, defines["SPR_PLAYER_BASE"], 0,
        player_x, player_y, MODE_8X16, 0)
    sprites += metasprite_sprites(
        accent_meta, defines["SPR_ACCENT_BASE"], 0,
        accent_x, accent_y, MODE_8X8, FLIP_H | FLIP_V)
    render_sprites(frame, sprite_data, defines["SPR_TILE_FIRST"], sprites)

    try:
        Path(args.out).write_bytes(frame)
    except OSError as exc:
        print("ref_render: cannot write {}: {}".format(args.out, exc),
              file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
