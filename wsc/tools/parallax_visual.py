#!/usr/bin/env python3
"""Visual parallax-band check, independent of the engine RAM oracle.

Runs the same scene on the GB oracle ROM and on the WSC gamerom at a few
engine ticks, captures both frames (wsrun --raw), and compares each parallax
band's background against the GB frame.  The GB frame is the reference
render: if the WSC line-match ISR wrote the right screen-1 scroll for every
band, the band's tile pattern is at horizontal offset 0 from the GB band.

The comparison uses a binary horizontal-edge map, so the two platforms'
different colour output does not matter.  It only looks at the 160 px wide
logical screen (centred at x=32 on WSC), which is the same viewport as GB.
"""

import argparse
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import gbdiff as g  # noqa: E402

BAND_MARGIN = 4          # lines away from a GB next_y boundary
EDGE_THRESHOLD = 8       # luminance step that counts as an edge
MAX_SHIFT = 12           # horizontal search range, pixels
LOGICAL_X = 32           # WSC 160 px margin (224 - 160) / 2
LOGICAL_W = 160


def luminance(raw, width, x, y):
    i = (y * width + x) * 3
    return (raw[i] * 299 + raw[i + 1] * 587 + raw[i + 2] * 114) // 1000


def edge(raw, width, x, y):
    return 1 if abs(luminance(raw, width, x, y) -
                    luminance(raw, width, x + 1, y)) > EDGE_THRESHOLD else 0


def band_score(gb_raw, wsc_raw, first, last, shift):
    total = 0
    count = 0
    for y in range(first, last):
        for x in range(12, 148):
            sx = LOGICAL_X + x + shift
            if not (LOGICAL_X <= sx < LOGICAL_X + LOGICAL_W - 1):
                continue
            total += abs(edge(gb_raw, LOGICAL_W, x, y) -
                         edge(wsc_raw, 224, sx, y))
            count += 1
    if not count:
        return 1.0
    return total / count


def band_shifts(gb_raw, wsc_raw, first, last):
    scores = [(band_score(gb_raw, wsc_raw, first, last, d), d)
              for d in range(-MAX_SHIFT, MAX_SHIFT + 1)]
    scores.sort(key=lambda item: (item[0], abs(item[1]), item[1]))
    return scores


def run_frame(args, what):
    out = g.run(args, what=what)
    match = re.search(r"width=(\d+) height=(\d+)", out)
    if not match:
        raise g.OracleError("{} produced no frame size".format(what))
    return int(match.group(1)), int(match.group(2))


def gb_args(config, rom, layout, symbols, tick, raw, trace):
    start_x = int(config["gb"]["startX"]) * 256
    start_y = int(config["gb"]["startY"]) * 256
    player = symbols["_actors"]
    args = [
        g.WSRUN, "--core", g.GB_CORE, "--rom", rom,
        "--frames", str(config.get("frames", 20000)),
        "--marker-timeout", str(config.get("marker_timeout", 2500)),
        "--tick", "{}:1".format(g.gb_ram_offset(
            symbols["_game_time"], 0x8000)),
        "--tick-gate", "{}:1".format(g.gb_ram_offset(
            symbols["_vm_exception_code"], 0x8000)),
        "--max-ticks", str(tick),
        "--trace", str(trace),
        "--raw", str(raw),
        "--marker", "{}:1:0".format(g.gb_ram_offset(
            symbols["_game_time"], 0x8000)),
        "--marker", "{}:2:{}".format(
            g.gb_ram_offset(player + layout["x"], 0x8000), start_x),
        "--marker", "{}:2:{}".format(
            g.gb_ram_offset(player + layout["y"], 0x8000), start_y),
    ]
    if config.get("input"):
        args.extend(["--input", config["input"], "--input-tick"])
    return args


def wsc_args(config, symbols, layout, tick, raw, png, trace):
    start_x = int(config["gb"]["startX"]) * 256
    start_y = int(config["gb"]["startY"]) * 256
    player = symbols["actors"]
    args = [
        g.WSRUN, "--core", g.WSC_CORE, "--rom", g.WSC_ROM,
        "--boot-id", str(config["wsc"]["bootId"]),
        "--frames", str(config.get("frames", 20000)),
        "--marker-timeout", str(config.get("marker_timeout", 2500)),
        "--tick", "{}:1".format(symbols["game_time"]),
        "--tick-gate", "{}:1".format(symbols["vm_exception_code"]),
        "--max-ticks", str(tick),
        "--trace", str(trace),
        "--raw", str(raw),
        "--png", str(png),
        "--screen-width", "160",
        "--marker", "{}:1:1".format(symbols[config["wsc"]["readySymbol"]]),
        "--marker", "{}:1:0".format(symbols["game_time"]),
        "--marker", "{}:2:{}".format(player + layout["x"], start_x),
        "--marker", "{}:2:{}".format(player + layout["y"], start_y),
    ]
    if config.get("input"):
        args.extend(["--input", config["input"], "--input-tick"])
    return args


def gb_bands(trace, symbols, tick):
    """Interior line ranges and source SCX for each GB band at tick."""
    data = g.GBTrace(trace)
    data.current = tick
    base = symbols["_parallax_rows"]
    next_y = []
    scx = []
    for band in range(3):
        next_y.append(data.u8(base + band * 6 + 1))
        scx.append(data.u8(base + band * 6))
    # next_y == 0 marks the last band; use the screen height for its end.
    ends = [n if n else 144 for n in next_y]
    bands = []
    start = 0
    for end, value in zip(ends, scx):
        first = min(start + BAND_MARGIN, 144)
        last = max(first, end - BAND_MARGIN)
        bands.append((first, last, value))
        start = end
    return bands


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=str(
        g.ORACLE_DIR / "platform-parallax.json"))
    parser.add_argument("--ticks", default="100,200,300")
    parser.add_argument("--png-out", default=None,
                        help="copy the last captured WSC frame here")
    parser.add_argument("--workdir", default=None)
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = (g.ROOT / config_path).resolve()
    config = g.load_config(config_path)
    if config.get("input"):
        config["input"] = str((config_path.parent / config["input"]).resolve())
    ticks = [int(t) for t in args.ticks.split(",") if t.strip()]
    if not ticks:
        raise g.OracleError("no ticks requested")
    workdir = Path(args.workdir) if args.workdir else (
        g.BUILD / "parallax-visual")
    workdir.mkdir(parents=True, exist_ok=True)

    g.ensure_wsrun()
    g.ensure_gb_core()
    g.ensure_wsc_rom()
    gbdk = g.ensure_gbdk()
    oracle_workdir = g.BUILD / "gb-oracle" / config["name"]
    rom, noi = g.prepare_gb_project(config, oracle_workdir)
    gb_symbols = g.parse_noi(noi)
    wsc_symbols = g.wsc_symbols(g.WSC_ELF)
    gb_layout = g.gb_layout(oracle_workdir, gbdk, g.cli_tmp_dir(config))
    wsc_layout = g.wsc_layout(oracle_workdir)

    failures = 0
    last_png = None
    for tick in ticks:
        gb_raw_path = workdir / "gb-{}.raw".format(tick)
        wsc_raw_path = workdir / "wsc-{}.raw".format(tick)
        gb_trace = workdir / "gb-{}.trace".format(tick)
        wsc_trace = workdir / "wsc-{}.trace".format(tick)
        wsc_png = workdir / "wsc-{}.png".format(tick)
        last_png = wsc_png
        run_frame(gb_args(config, rom, gb_layout, gb_symbols,
                          tick, gb_raw_path, gb_trace),
                  "GB frame at tick {}".format(tick))
        width, height = run_frame(
            wsc_args(config, wsc_symbols, wsc_layout, tick, wsc_raw_path,
                     wsc_png, wsc_trace),
            "WSC frame at tick {}".format(tick))
        if width != 224 or height != 144:
            raise g.OracleError("unexpected WSC frame size {}x{}".format(
                width, height))
        gb_raw = gb_raw_path.read_bytes()
        wsc_raw = wsc_raw_path.read_bytes()
        print("tick {}:".format(tick))
        for band, (first, last, expected) in enumerate(
                gb_bands(gb_trace, gb_symbols, tick)):
            scores = band_shifts(gb_raw, wsc_raw, first, last)
            zero = [score for score, shift in scores if shift == 0][0]
            other = min(score for score, shift in scores if shift != 0)
            best_score, best_shift = scores[0]
            ok = (best_shift == 0 and zero < 0.15 and zero < other * 0.9)
            print("  band {} lines {}-{} GB scx {}: visual shift {} "
                  "(mismatch {:.4f}, next {:.4f}) {}".format(
                      band, first, last - 1, expected, best_shift, zero,
                      other, "OK" if ok else "FAIL"))
            if not ok:
                failures += 1

    if args.png_out:
        out = Path(args.png_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(last_png.read_bytes())
        print("saved {} (WSC frame at tick {})".format(out, ticks[-1]))
    if failures:
        print("FAIL parallax-visual: {} band(s) at a non-zero offset or "
              "ambiguous".format(failures))
        return 1
    print("PASS parallax-visual: {} ticks, {} bands at offset 0".format(
        len(ticks), len(ticks) * 3))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except g.OracleError as exc:
        print("parallax-visual: {}".format(exc), file=sys.stderr)
        sys.exit(2)
