#!/usr/bin/env python3
"""Vertical-mode frame check.

Boots the WSC gamerom in a chosen logical orientation, captures the physical
224x144 frame at one or more engine ticks, rotates it back to the logical
coordinate system and compares it byte for byte with a reference render of
the same scene at the camera position read from RAM.

The vertical mapping implemented by the HAL is

    physical x = 223 - logical y
    physical y = logical x

so the inverse is ``logical x = physical y``, ``logical y = 223 - physical x``.
"""

import argparse
import struct
import subprocess
import sys
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
WSC = HERE.parent
ROOT = WSC.parent
sys.path.insert(0, str(HERE))

import boot_oracle as boot  # noqa: E402
import gbdiff  # noqa: E402
import ref_render  # noqa: E402

DEFAULT_EXPORT = WSC / "build" / "export"
DEFAULT_PROJECT = ROOT / "appData" / "templates" / "gbs2"
WSRUN = WSC / "build" / "wsrun"
CORE = WSC / "build" / "mednafen_wswan_libretro.so"
ROM = WSC / "gamerom" / "gamerom.wsc"
ELF = WSC / "gamerom" / "build" / "gamerom.elf"
WORKDIR = WSC / "build" / "c35"

PHYSICAL_W = 224
PHYSICAL_H = 144
LOGICAL_W = 144
LOGICAL_H = 224


class VisualError(Exception):
    pass


def read_u16(ram, address):
    if address + 2 > len(ram):
        raise VisualError("RAM address 0x{:04X} is outside the dump".format(address))
    return int.from_bytes(ram[address:address + 2], "little")


def read_u8(ram, address):
    if address >= len(ram):
        raise VisualError("RAM address 0x{:04X} is outside the dump".format(address))
    return ram[address]


def write_png(path, width, height, rgb):
    def chunk(tag, data):
        body = tag + data
        return (struct.pack(">I", len(data)) + body +
                struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF))

    rows = b"".join(
        b"\x00" + rgb[y * width * 3:(y + 1) * width * 3]
        for y in range(height)
    )
    png = (b"\x89PNG\r\n\x1a\n" +
           chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)) +
           chunk(b"IDAT", zlib.compress(rows, 9)) +
           chunk(b"IEND", b""))
    path.write_bytes(png)


def unrotate_vertical(raw):
    """Map the physical 224x144 frame back to the logical 144x224 view."""
    out = bytearray(LOGICAL_W * LOGICAL_H * 3)
    for py in range(PHYSICAL_H):
        for px in range(PHYSICAL_W):
            lx = py
            ly = (LOGICAL_H - 1) - px
            src = (py * PHYSICAL_W + px) * 3
            dst = (ly * LOGICAL_W + lx) * 3
            out[dst:dst + 3] = raw[src:src + 3]
    return out


def compare_frames(actual, reference, width, label):
    if len(actual) != len(reference):
        raise VisualError("{}: frame sizes differ ({} vs {})".format(
            label, len(actual), len(reference)))
    for offset, (got, want) in enumerate(zip(actual, reference)):
        if got != want:
            pixel = offset // 3
            x, y = pixel % width, pixel // width
            start = pixel * 3
            raise VisualError(
                "{}: mismatch at logical pixel ({}, {}): wsrun {} != "
                "reference {}".format(
                    label, x, y,
                    tuple(actual[start:start + 3]),
                    tuple(reference[start:start + 3])))


def run_wsrun(boot_id, orientation, tick, out_dir, tag):
    out_dir.mkdir(parents=True, exist_ok=True)
    raw_path = out_dir / (tag + ".rgb")
    ram_path = out_dir / (tag + ".ram")
    tick_address = boot.elf_symbol_address(ELF, "game_time")
    argv = [
        str(WSRUN), "--core", str(CORE), "--rom", str(ROM),
        "--boot-id", str(boot_id),
        "--orientation", orientation,
        "--frames", "5000",
        "--tick", "{}:1".format(tick_address),
        "--max-ticks", str(tick),
        "--raw", str(raw_path), "--ram", str(ram_path),
    ]
    proc = subprocess.run(argv, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, text=True)
    if proc.returncode != 0:
        raise VisualError("wsrun failed: {}".format(
            (proc.stderr or proc.stdout).strip().splitlines()[-1:]))
    return raw_path.read_bytes(), ram_path.read_bytes()


def build_reference(export, project, scene, start_x, start_y, orientation,
                    ram, layout, tick, init_effects=None, timer_runs=None):
    symbols = {
        name: boot.elf_symbol_address(ELF, name)
        for name in ("scroll_x", "scroll_y", "scroll_center_x",
                     "scroll_center_y", "camera_x", "camera_y", "actors",
                     "actors_len")
    }
    scroll_x = read_u16(ram, symbols["scroll_x"])
    scroll_y = read_u16(ram, symbols["scroll_y"])
    center_x = read_u16(ram, symbols["scroll_center_x"])
    center_y = read_u16(ram, symbols["scroll_center_y"])
    camera_x = read_u16(ram, symbols["camera_x"])
    camera_y = read_u16(ram, symbols["camera_y"])
    player_x = read_u16(ram, symbols["actors"] + layout["x"]) >> 5
    player_y = read_u16(ram, symbols["actors"] + layout["y"]) >> 5
    player_frame = read_u8(ram, symbols["actors"] + layout["frame"])

    if orientation == "vertical":
        screen_w, screen_h = LOGICAL_W, LOGICAL_H
    else:
        screen_w, screen_h = PHYSICAL_W, PHYSICAL_H

    start_dir = boot.parse_start_dir(export.export_dir)
    scene_meta = export.scene(scene)
    effects = init_effects
    if effects is None:
        effects = (boot.parse_init_script(export.export_dir,
                                          scene_meta["script_init"])
                   if scene_meta["script_init"] else {})

    # Take every scene actor's frame and position from RAM, and drop actors
    # the engine has not activated by this tick.
    actor_overrides = {}
    inactive = set(effects.get("deactivated_actors", ()))
    actors_len = read_u8(ram, symbols["actors_len"])
    for index in range(scene_meta["n_actors"]):
        ram_index = index + 1
        if ram_index >= actors_len:
            inactive.add(index)
            continue
        base = symbols["actors"] + ram_index * layout["size"]
        flags = read_u8(ram, base + layout["flags"])
        if not flags & 0x20:
            inactive.add(index)
            continue
        actor_overrides[index] = {
            "x": read_u16(ram, base + layout["x"]),
            "y": read_u16(ram, base + layout["y"]),
            "frame": read_u8(ram, base + layout["frame"]),
        }
    effects = dict(effects)
    effects["deactivated_actors"] = inactive

    _, _, _, scenario, _ = boot.build_scene(
        export, project, scene, start_x, start_y, start_dir, 0,
        effects=effects,
        final={
            "source_x": scroll_x,
            "source_y": scroll_y,
            "camera_x": camera_x,
            "camera_y": camera_y,
            "player_x": player_x,
            "player_y": player_y,
            "player_frame": player_frame,
            "actor_overrides": actor_overrides,
        },
        timer_runs=(tick // 16 if timer_runs is None else timer_runs),
        screen_w=screen_w, screen_h=screen_h)
    scenario["scroll_x"] = (scroll_x - center_x) & 0xFF
    scenario["scroll_y"] = (scroll_y - center_y) & 0xFF
    return scenario

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--export", default=str(DEFAULT_EXPORT))
    parser.add_argument("--project-dir", default=str(DEFAULT_PROJECT))
    parser.add_argument("--boot", type=int, required=True,
                        help="wsrun boot id")
    parser.add_argument("--scene", required=True)
    parser.add_argument("--start-x", type=int, default=0,
                        help="player start x in pixels")
    parser.add_argument("--start-y", type=int, default=0)
    parser.add_argument("--orientation", choices=("vertical", "horizontal"),
                        default="vertical")
    parser.add_argument("--ticks", default="100,200,300")
    parser.add_argument("--png-out", default=None,
                        help="write the last logical frame as PNG")
    parser.add_argument("--raw-out", default=None,
                        help="write the last logical frame as RGB24")
    parser.add_argument("--workdir", default=str(WORKDIR))
    args = parser.parse_args(argv)

    ticks = [int(t) for t in args.ticks.split(",") if t]
    if not ticks:
        raise VisualError("no ticks given")

    try:
        export = boot.ExportData(args.export)
        project = args.project_dir
        out_dir = Path(args.workdir) / "visual"
        out_dir.mkdir(parents=True, exist_ok=True)
        layout = gbdiff.wsc_layout(out_dir)
        failures = 0
        last_logical = None
        for tick in ticks:
            tag = "{}-{}-t{}".format(args.scene, args.orientation, tick)
            raw, ram = run_wsrun(args.boot, args.orientation, tick,
                                 out_dir, tag)
            scenario = build_reference(export, project, args.scene,
                                       args.start_x, args.start_y,
                                       args.orientation, ram, layout, tick)
            reference_path = out_dir / (tag + ".ref")
            ref_render.render_scenario(scenario, reference_path)
            reference = reference_path.read_bytes()
            if args.orientation == "vertical":
                logical = unrotate_vertical(raw)
                width, height = LOGICAL_W, LOGICAL_H
            else:
                logical = raw
                width, height = PHYSICAL_W, PHYSICAL_H
            last_logical = (width, height, logical)
            try:
                compare_frames(logical, reference, width, tick)
                print("tick {}: {}x{} exact match".format(
                    tick, width, height))
            except VisualError as exc:
                failures += 1
                print("tick {}: {}".format(tick, exc))
        if failures:
            print("FAIL vertical-visual: {} of {} ticks differ".format(
                failures, len(ticks)))
            return 1
        if args.png_out:
            width, height, logical = last_logical
            write_png(Path(args.png_out), width, height, logical)
            print("saved {} ({}x{}, tick {})".format(
                args.png_out, width, height, ticks[-1]))
        if args.raw_out:
            Path(args.raw_out).write_bytes(last_logical[2])
        print("PASS vertical-visual: {} ticks {}x{}".format(
            len(ticks), last_logical[0], last_logical[1]))
        return 0
    except (VisualError, boot.OracleError, OSError, KeyError, ValueError) as exc:
        print("vertical_visual: {}".format(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
