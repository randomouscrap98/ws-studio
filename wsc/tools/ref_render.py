#!/usr/bin/env python3
"""Render the expected C05 background frame from the ROM's GB-format data.

The data arrays are parsed from the hand-written C source so the ROM and this
renderer share one source of truth.  The output is the 224x144 RGB24 frame as
wsrun emits it: WSC RGB444 colours expanded exactly as beetle-wswan's
RGB565 output plus wsrun's RGB565->RGB24 conversion, i.e. nibble*17 truncated
to 5/6 bits and then bit-replicated.  That makes an exact byte comparison
valid for the pinned emulator.
"""
import argparse
import re
import sys
from pathlib import Path

WIDTH = 224
HEIGHT = 144
TILE = 8


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


def render(arrays, scroll):
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

    out = bytearray(WIDTH * HEIGHT * 3)
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
    return bytes(out)


def main():
    default_data = Path(__file__).resolve().parent.parent / "halrom" / "src" / "bg_data.c"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", default=str(default_data),
                        help="bg_data.c to read (default: wsc/halrom/src/bg_data.c)")
    parser.add_argument("--scroll", type=int, default=0,
                        help="horizontal scroll in pixels")
    parser.add_argument("--out", required=True, help="output RGB24 file")
    args = parser.parse_args()

    try:
        arrays = parse_arrays(Path(args.data))
    except OSError as exc:
        print("ref_render: cannot read {}: {}".format(args.data, exc),
              file=sys.stderr)
        return 2

    required = ("bg_tiles", "bg_tiles_hi", "bg_palettes", "bg_map", "bg_attrs")
    missing = [name for name in required if name not in arrays]
    if missing:
        print("ref_render: missing arrays: {}".format(", ".join(missing)),
              file=sys.stderr)
        return 2

    frame = render(arrays, args.scroll)
    try:
        Path(args.out).write_bytes(frame)
    except OSError as exc:
        print("ref_render: cannot write {}: {}".format(args.out, exc),
              file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
