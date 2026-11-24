#!/usr/bin/env python3
"""Oracle for the topdown walking tests.

Simulates the engine's topdown movement (src/states/topdown.c), collision
tests (src/core/collision.c) and the camera/scroll follow rules
(src/core/camera.c, src/core/scroll.c) from the exported collision map and
the same input file that wsrun feeds to the ROM. The final player position is
then handed to boot_oracle.build_scene(), which renders the expected frame
through ref_render.py and writes the RAM checks.
"""

import argparse
import re
import sys
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

# GB J_* bits used by input.c.
J_RIGHT = 0x01
J_LEFT = 0x02
J_UP = 0x04
J_DOWN = 0x08
J_A = 0x10
J_B = 0x20
J_SELECT = 0x40
J_START = 0x80
DPAD = J_UP | J_DOWN | J_LEFT | J_RIGHT

# The buttons wsrun can put in an input file, mapped to the GB bits the WSC
# HAL produces for the matching WonderSwan button.
BUTTONS = {
    "X1": J_UP,
    "X2": J_RIGHT,
    "X3": J_DOWN,
    "X4": J_LEFT,
    "Y1": J_SELECT,
    "A": J_A,
    "B": J_B,
    "START": J_START,
}

# topdown.c direction_e values.
DIR_DOWN = 0
DIR_RIGHT = 1
DIR_UP = 2
DIR_LEFT = 3

COLLISION_TOP = 0x01
COLLISION_BOTTOM = 0x02
COLLISION_LEFT = 0x04
COLLISION_RIGHT = 0x08
COLLISION_ALL = 0x0F


class WalkError(Exception):
    pass


def resolve_input(path):
    candidate = Path(path)
    if candidate.is_file():
        return candidate
    for base in (WSC, ROOT):
        candidate = base / path
        if candidate.is_file():
            return candidate
    raise WalkError("input file {} does not exist".format(path))


def read_input(path):
    """Return a sorted list of (frame, GB mask), like wsrun's parser."""
    events = []
    for number, line in enumerate(resolve_input(path).read_text().splitlines(), 1):
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        fields = line.split(None, 1)
        if len(fields) != 2:
            raise WalkError("input line {}: expected FRAME BUTTONS".format(number))
        try:
            frame = int(fields[0], 10)
        except ValueError as exc:
            raise WalkError("input line {}: bad frame".format(number)) from exc
        mask = 0
        tokens = [token.strip() for token in fields[1].split(",")]
        if tokens == ["-"]:
            pass
        else:
            for token in tokens:
                if token not in BUTTONS:
                    raise WalkError(
                        "input line {}: unknown button {}".format(number, token)
                    )
                mask |= BUTTONS[token]
        events.append((frame, mask))
    events.sort()
    for previous, current in zip(events, events[1:]):
        if previous[0] == current[0]:
            raise WalkError("input file sets frame {} twice".format(current[0]))
    return events


def mask_at(events, frame):
    mask = 0
    for event_frame, event_mask in events:
        if event_frame > frame:
            break
        mask = event_mask
    return mask


def subpx_expr(expr):
    """Evaluate the simple PX_TO_SUBPX/TILE_TO_SUBPX expressions in bounds."""
    expr = re.sub(
        r"PX_TO_SUBPX\s*\(\s*(-?\d+)\s*\)",
        lambda match: str(int(match.group(1)) * 32),
        expr,
    )
    expr = re.sub(
        r"TILE_TO_SUBPX\s*\(\s*(-?\d+)\s*\)",
        lambda match: str(int(match.group(1)) * 256),
        expr,
    )
    try:
        return int(eval(expr, {"__builtins__": {}}, {}))
    except (SyntaxError, TypeError, ValueError) as exc:
        raise WalkError("cannot evaluate bounds expression {!r}".format(expr)) from exc


def sprite_bounds(export, symbol):
    text = export.text(symbol)
    body = boot.field_body(text, "bounds")
    bounds = {}
    for field in ("left", "right", "top", "bottom"):
        match = re.search(
            r"\." + re.escape(field) + r"\s*=\s*([^,\n}]+)", body
        )
        if not match:
            raise WalkError("{} bounds.{} is missing".format(symbol, field))
        bounds[field] = subpx_expr(match.group(1).strip())
    return bounds


def init_value(export, name, default):
    """Read a platform global from the exported script_engine_init.s."""
    path = Path(export.export_dir) / "src" / "data" / "script_engine_init.s"
    if not path.is_file():
        return default
    text = path.read_text()
    if name == "topdown_grid":
        match = re.search(
            r"\.R_INT8\s+(-?\d+)\s*\n\s*\.R_REF_MEM_SET\s+\.MEM_I8,\s*_topdown_grid",
            text,
        )
    else:
        match = re.search(
            r"_" + re.escape(name) + r"::\s*\n\s*\.db\s+(-?\d+)\s*$",
            text,
            re.M,
        )
    return int(match.group(1), 0) if match else default


def load_collision(export, scene_symbol):
    scene = export.scene(scene_symbol)
    text = export.text(scene_symbol)
    match = re.search(
        r"\.collisions\s*=\s*TO_FAR_PTR_T\s*\(\s*(\w+)\s*\)", text
    )
    if not match:
        raise WalkError("{} has no collision map".format(scene_symbol))
    symbol = match.group(1)
    body = boot.array_body(export.text(symbol), symbol)
    return [int(token, 0) for token in re.findall(boot.NUM, body)]


def collision_at(collision, width, height, tx, ty, mask):
    if tx >= width or ty >= height:
        return COLLISION_ALL & mask
    return collision[ty * width + tx] & mask


def range_y(collision, width, height, mask, tx, ty_start, ty_end):
    """tile_col_test_range_y() from collision.c."""
    if tx >= width or ty_start >= height:
        return bool(COLLISION_ALL & mask)
    inc = ty_start < ty_end
    ty = ty_start
    while True:
        if collision_at(collision, width, height, tx, ty, mask):
            return True
        if ty == ty_end:
            return False
        ty += 1 if inc else -1
        if ty >= height:
            return bool(COLLISION_ALL & mask)


def range_x(collision, width, height, mask, ty, tx_start, tx_end):
    """tile_col_test_range_x() from collision.c."""
    if tx_start >= width or ty >= height:
        return bool(COLLISION_ALL & mask)
    inc = tx_start < tx_end
    tx = tx_start
    while True:
        if collision_at(collision, width, height, tx, ty, mask):
            return True
        if tx == tx_end:
            return False
        tx += 1 if inc else -1
        if tx >= width:
            return bool(COLLISION_ALL & mask)


def simulate(export, scene_symbol, start_x, start_y, start_dir, grid, speed,
             bounds, events, frames):
    """Run the per-frame topdown state machine and return the final player."""
    collision = load_collision(export, scene_symbol)
    scene = export.scene(scene_symbol)
    width, height = scene["width"], scene["height"]

    x = (start_x * 32) & 0xFFFF
    y = (start_y * 32) & 0xFFFF
    if grid == 16:
        x &= 0xFE00
        y = (y & 0xFE00) + 0x0100
    else:
        x &= 0xFF00
        y &= 0xFF00

    direction = start_dir
    moving = False
    max_pos = 0
    last_joy = 0
    recent_joy = 0
    tile_offset = 2 if grid == 16 else 1

    for frame in range(frames):
        joy = mask_at(events, frame)
        if (joy ^ last_joy) & DPAD:
            recent_joy = (joy & ~last_joy) & DPAD

        on_grid = (
            (((x >> 5) & 15) == 0 and ((y >> 5) & 15) == 8)
            if grid == 16
            else ((x | y) & 0xFF) == 0
        )

        if on_grid:
            moving = False
            new_dir = None

            if recent_joy & J_LEFT:
                moving = True
                new_dir = DIR_LEFT
                ty_start = (y + bounds["top"]) >> 8
                ty_end = (y + bounds["bottom"]) >> 8
                tx = (x + bounds["left"]) >> 8
                if range_y(collision, width, height, COLLISION_RIGHT,
                           tx - 1, ty_start, ty_end):
                    moving = False
            elif recent_joy & J_RIGHT:
                moving = True
                new_dir = DIR_RIGHT
                ty_start = (y + bounds["top"]) >> 8
                ty_end = (y + bounds["bottom"]) >> 8
                tx = (x + bounds["right"]) >> 8
                if range_y(collision, width, height, COLLISION_LEFT,
                           tx + 1, ty_start, ty_end):
                    moving = False
            elif recent_joy & J_UP:
                moving = True
                new_dir = DIR_UP
                tx_start = (x + bounds["left"]) >> 8
                tx_end = (x + bounds["right"]) >> 8
                ty = (y + bounds["top"]) >> 8
                if range_x(collision, width, height, COLLISION_BOTTOM,
                           ty - 1, tx_start, tx_end):
                    moving = False
            elif recent_joy & J_DOWN:
                moving = True
                new_dir = DIR_DOWN
                tx_start = (x + bounds["left"]) >> 8
                tx_end = (x + bounds["right"]) >> 8
                ty = (y + bounds["bottom"]) >> 8
                if range_x(collision, width, height, COLLISION_TOP,
                           ty + 1, tx_start, tx_end):
                    moving = False

            if new_dir is not None:
                direction = new_dir

            if direction == DIR_RIGHT:
                max_pos = (((x >> 8) + tile_offset) & 0xFF) << 8
            elif direction == DIR_LEFT:
                max_pos = (((x >> 8) - tile_offset) & 0xFF) << 8
            elif direction == DIR_DOWN:
                max_pos = (((y >> 8) + tile_offset) & 0xFF) << 8
            elif direction == DIR_UP:
                max_pos = (((y >> 8) - tile_offset) & 0xFF) << 8

        if moving:
            if direction == DIR_RIGHT:
                x = (x + speed) & 0xFFFF
            elif direction == DIR_LEFT:
                x = (x - speed) & 0xFFFF
            elif direction == DIR_DOWN:
                y = (y + speed) & 0xFFFF
            elif direction == DIR_UP:
                y = (y - speed) & 0xFFFF

            if direction == DIR_RIGHT:
                if x > max_pos:
                    x = max_pos
            elif direction == DIR_LEFT:
                if x < max_pos:
                    x = max_pos
                elif max_pos == 0 and x >= 0xFFFF - speed:
                    x = 0
            elif direction == DIR_DOWN:
                if y > max_pos:
                    y = max_pos
            elif direction == DIR_UP:
                if y < max_pos:
                    y = max_pos
                elif max_pos == 0 and y >= 0xFFFF - speed:
                    y = 0

        last_joy = joy

    if x & 0x1F or y & 0x1F:
        raise WalkError(
            "player is still between pixels at frame {} ({}, {})".format(
                frames, x / 32.0, y / 32.0
            )
        )
    return x >> 5, y >> 5, direction


def wsc_actor_overrides(ram_path, elf_path):
    """Read the live actor transforms from the WSC RAM dump.

    Actors with update scripts (the town Pet Owner) move while the walk test
    runs. The map, tiles, palettes and sprite drawing still come from the
    exported data; only each actor's position and metasprite frame come from
    the emulated WSC so the reference frame matches what the engine rendered.
    """
    ram = Path(ram_path).read_bytes()
    symbols = gbdiff.wsc_symbols(Path(elf_path))
    workdir = WSC / "build" / "walk-oracle-layout"
    workdir.mkdir(parents=True, exist_ok=True)
    layout = gbdiff.wsc_layout(workdir)
    if "actors" not in symbols:
        raise WalkError("actors symbol not found in {}".format(elf_path))
    base = symbols["actors"]
    overrides = {}
    # build_scene() numbers the exported actor array from 0; the engine keeps
    # the player in actors[0], so engine index = exported index + 1.
    for index in range(0, layout["count"] - 1):
        engine_index = index + 1
        def read(field, size):
            offset = base + engine_index * layout["size"] + layout[field]
            if offset + size > len(ram):
                raise WalkError("actor {} is outside the RAM dump".format(
                    engine_index))
            return int.from_bytes(ram[offset:offset + size], "little")
        overrides[index] = {
            "x": read("x", 2),
            "y": read("y", 2),
            "frame": read("frame", 1),
        }
    return overrides


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--export", default=str(DEFAULT_EXPORT))
    parser.add_argument("--project-dir", default=str(DEFAULT_PROJECT))
    parser.add_argument("--scene", required=True)
    parser.add_argument("--start-x", type=int, required=True,
                        help="player start x in pixels")
    parser.add_argument("--start-y", type=int, required=True,
                        help="player start y in pixels")
    parser.add_argument("--input", required=True, help="wsrun input file")
    parser.add_argument("--frames", type=int, required=True)
    parser.add_argument("--out", help="write the expected RGB24 frame")
    parser.add_argument("--ram-out", help="write the RAM checks JSON")
    parser.add_argument("--elf", help="ELF used by the RAM checks")
    parser.add_argument("--wsc-ram",
                        help="WSC system-RAM dump used for live actor transforms")
    parser.add_argument("--wsc-elf",
                        help="WSC ELF that defines the actor layout")
    args = parser.parse_args(argv)

    try:
        export = boot.ExportData(args.export)
        scene = export.scene(args.scene)
        player_sprite = scene["player_sprite"]
        if not player_sprite:
            raise WalkError("{} has no player sprite".format(args.scene))
        bounds = sprite_bounds(export, player_sprite)
        grid = init_value(export, "topdown_grid", 8)
        speed = init_value(export, "start_player_move_speed", 32)
        start_dir = boot.parse_start_dir(args.export)
        events = read_input(args.input)
        final_x, final_y, final_dir = simulate(
            export, args.scene, args.start_x, args.start_y, start_dir, grid,
            speed, bounds, events, args.frames
        )

        final = {}
        if args.wsc_ram or args.wsc_elf:
            if not (args.wsc_ram and args.wsc_elf):
                raise WalkError("--wsc-ram and --wsc-elf go together")
            final["actor_overrides"] = wsc_actor_overrides(
                args.wsc_ram, args.wsc_elf
            )

        # build_scene() applies the camera and scroll rules to this position,
        # renders the visible cells from the exported map and writes the
        # expected camera/player RAM values.
        _scene, _background, actor_info, scenario, expected = boot.build_scene(
            export, args.project_dir, args.scene, final_x, final_y, final_dir,
            args.frames, final=final
        )

        if args.out:
            ref_render.render_scenario(scenario, args.out)
        if args.ram_out:
            if not args.elf:
                raise WalkError("--ram-out requires --elf")
            ram_args = argparse.Namespace(
                export=args.export, elf=args.elf, ram_out=args.ram_out
            )
            boot.write_ram_checks(ram_args, _scene, actor_info, expected)
    except (WalkError, boot.OracleError, OSError, KeyError, ValueError) as exc:
        print("walk_oracle: {}".format(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
