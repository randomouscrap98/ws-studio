#!/usr/bin/env python3
"""Oracle for the WSC engine boot tests.

Reads the exported GB Studio C data (not the WSC build tree) and the project
JSON, simulates the engine's scene load, sprite-tile allocation, actor
activation and camera/scroll rules, and hands a WSC hardware scenario to
ref_render.py. Also emits the RAM checks for the test runner.

The expected frame is the static scene at rest (the idle animations on these
scenes are single-frame), so the frame count only needs to be large enough for
the boot to settle.
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WSC = HERE.parent
ROOT = WSC.parent
sys.path.insert(0, str(HERE))
import ref_render  # noqa: E402

DEFAULT_EXPORT = WSC / "build" / "export"
DEFAULT_PROJECT = ROOT / "appData" / "templates" / "gbs2"

NUM = r"-?0x[0-9A-Fa-f]+|-?\d+"
DIRS = {"DIR_DOWN": 0, "DIR_RIGHT": 1, "DIR_UP": 2, "DIR_LEFT": 3}


class OracleError(Exception):
    pass


def strip_comments(text):
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return re.sub(r"//[^\n]*", "", text)


def brace_body(text, marker):
    match = re.search(marker, text)
    if not match:
        raise OracleError("marker not found: {}".format(marker))
    start = match.end()
    depth = 1
    i = start
    while i < len(text):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[start:i]
        i += 1
    raise OracleError("unterminated body for {}".format(marker))


def array_body(text, name):
    return brace_body(text, r"\b" + re.escape(name) + r"\s*\[\s*\]\s*=\s*\{")


def field_body(text, field):
    return brace_body(text, r"\." + re.escape(field) + r"\s*=\s*\{")


def ints(body):
    return [int(token, 0) for token in re.findall(NUM, body)]


def field_int(text, field, default=0):
    match = re.search(r"\." + re.escape(field) + r"\s*=\s*(" + NUM + ")", text)
    return int(match.group(1), 0) if match else default


def field_ptr(text, field):
    match = re.search(
        r"\." + re.escape(field) + r"\s*=\s*TO_FAR_PTR_T\s*\(\s*(\w+)\s*\)", text
    )
    return match.group(1) if match else None


def field_ref(text, field):
    match = re.search(r"\." + re.escape(field) + r"\s*=\s*(\w+)", text)
    return match.group(1) if match else None


def split_entries(body):
    entries = []
    depth = 0
    start = None
    for i, ch in enumerate(body):
        if ch == "{":
            if depth == 0:
                start = i + 1
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start is not None:
                entries.append(body[start:i])
                start = None
    return entries


class ExportData:
    def __init__(self, export_dir):
        self.export_dir = Path(export_dir)
        data_dir = self.export_dir / "src" / "data"
        if not data_dir.is_dir():
            raise OracleError("export data directory {} is missing".format(data_dir))
        self.symbols = {}
        for path in sorted(data_dir.rglob("*.c")):
            text = strip_comments(path.read_text())
            self.symbols.setdefault(path.stem, (path, text))
            for match in re.finditer(
                r"^\s*(?:static\s+)?const\s+[^;=]*?\b(\w+)\s*(?:\[[^\]]*\])?\s*=",
                text,
                re.M,
            ):
                self.symbols.setdefault(match.group(1), (path, text))
        self._cache = {}

    def text(self, symbol):
        if symbol not in self.symbols:
            raise OracleError("exported symbol {} not found".format(symbol))
        return self.symbols[symbol][1]

    def tileset(self, symbol):
        text = self.text(symbol)
        count = field_int(text, "n_tiles")
        data = ints(field_body(text, "tiles"))
        if len(data) < count * 16:
            raise OracleError("{} has {} tile bytes for {}".format(
                symbol, len(data), count))
        return [data[i * 16:(i + 1) * 16] for i in range(count)]

    def palette(self, symbol):
        text = self.text(symbol)
        words = []
        for line in text.splitlines():
            if "CGB_PALETTE" not in line:
                continue
            inner = line[line.index("CGB_PALETTE"):]
            for rgb in re.findall(r"RGB\s*\(([^)]*)\)", inner):
                r, g, b = [int(v, 0) for v in rgb.split(",")]
                words.append((r & 0x1F) | ((g & 0x1F) << 5) | ((b & 0x1F) << 10))
        if not words:
            raise OracleError("no CGB palette entries in {}".format(symbol))
        return words

    def metasprite(self, symbol):
        text = self.text(symbol)
        body = array_body(text, symbol)
        return [
            [int(dy, 0), int(dx, 0), int(dtile, 0), int(props, 0)]
            for dy, dx, dtile, props in re.findall(
                r"\{\s*(" + NUM + r")\s*,\s*(" + NUM + r")\s*,\s*("
                + NUM + r")\s*,\s*(" + NUM + r")\s*\}", body)
        ]

    def spritesheet(self, symbol):
        if symbol in self._cache:
            return self._cache[symbol]
        text = self.text(symbol)
        meta_list_name = field_ref(text, "metasprites")
        animations_name = field_ref(text, "animations")
        lookup_name = field_ref(text, "animations_lookup")
        tileset_name = field_ptr(text, "tileset")
        meta_names = re.findall(r"\b(\w+)\b", array_body(text, meta_list_name))
        animations = [
            (int(a, 0), int(b, 0))
            for a, b in re.findall(
                r"\.start\s*=\s*(" + NUM + r")\s*,\s*\.end\s*=\s*(" + NUM + r")",
                self.text(animations_name),
                re.S,
            )
        ]
        lookup = ints(array_body(self.text(lookup_name), lookup_name))
        sheet = {
            "metasprites": [self.metasprite(name) for name in meta_names],
            "animations": animations,
            "lookup": lookup,
            "tiles": self.tileset(tileset_name),
        }
        self._cache[symbol] = sheet
        return sheet

    def actors(self, symbol):
        text = self.text(symbol)
        result = []
        for entry in split_entries(array_body(text, symbol)):
            pos = re.search(
                r"\.pos\s*=\s*\{\s*\.x\s*=\s*(" + NUM + r")\s*,\s*\.y\s*=\s*("
                + NUM + r")", entry, re.S)
            sprite = re.search(r"\.sprite\s*=\s*TO_FAR_PTR_T\s*\(\s*(\w+)\s*\)",
                               entry)
            direction = re.search(r"\.dir\s*=\s*(DIR_\w+)", entry)
            result.append({
                "x": int(pos.group(1), 0) if pos else 0,
                "y": int(pos.group(2), 0) if pos else 0,
                "sprite": sprite.group(1) if sprite else None,
                "dir": DIRS.get(direction.group(1), 0) if direction else 0,
                "reserve_tiles": field_int(entry, "reserve_tiles"),
                "anim_tick": field_int(entry, "anim_tick", 15),
            })
        return result

    def scene(self, symbol):
        text = self.text(symbol)
        return {
            "symbol": symbol,
            "width": field_int(text, "width"),
            "height": field_int(text, "height"),
            "n_actors": field_int(text, "n_actors"),
            "n_sprites": field_int(text, "n_sprites"),
            "background": field_ptr(text, "background"),
            "palette": field_ptr(text, "palette"),
            "sprite_palette": field_ptr(text, "sprite_palette"),
            "player_sprite": field_ptr(text, "player_sprite"),
            "actors": field_ptr(text, "actors"),
            "sprites": field_ptr(text, "sprites"),
            "script_init": field_ptr(text, "script_init"),
        }

    def background(self, symbol):
        text = self.text(symbol)
        return {
            "width": field_int(text, "width"),
            "height": field_int(text, "height"),
            "tileset": field_ptr(text, "tileset"),
            "tilemap": field_ptr(text, "tilemap"),
            "attrs": field_ptr(text, "cgb_tilemap_attr"),
        }

    def ptr_list(self, symbol):
        return re.findall(r"TO_FAR_PTR_T\s*\(\s*(\w+)\s*\)",
                          array_body(self.text(symbol), symbol))


def project_scene(project_dir, symbol):
    """Find the scene .gbsres for a symbol and return its JSON object."""
    scenes = Path(project_dir) / "project" / "scenes"
    if not scenes.is_dir():
        raise OracleError("project scenes directory {} is missing".format(scenes))
    for path in sorted(scenes.rglob("scene.gbsres")):
        try:
            data = json.loads(path.read_text())
        except (OSError, ValueError) as exc:
            raise OracleError("cannot read {}: {}".format(path, exc)) from exc
        if data.get("symbol") == symbol:
            return data
    raise OracleError("scene {} not found in project".format(symbol))


def parse_start_dir(export_dir):
    path = Path(export_dir) / "src" / "data" / "script_engine_init.s"
    if not path.is_file():
        return DIRS["DIR_RIGHT"]
    text = path.read_text()
    match = re.search(r"_start_scene_dir::\s*\n\s*\.db\s+\.(\w+)", text)
    return DIRS.get(match.group(1), DIRS["DIR_RIGHT"]) if match else DIRS["DIR_RIGHT"]


def clamp(value, low, high):
    return max(low, min(high, value))


def expand_metasprite(entries, base_tile, screen_x, screen_y, sprite_mode=16):
    sprites = []
    cur_x, cur_y = screen_x, screen_y
    for dy, dx, dtile, props in entries:
        cur_x += dx
        cur_y += dy
        tile = 256 + ((base_tile + dtile) & 0xFF)
        palette = props & 0x07
        flip_h = bool(props & 0x20)
        flip_v = bool(props & 0x40)
        if sprite_mode == 8:
            sprites.append([tile, cur_x, cur_y, flip_h, flip_v, palette])
            continue
        top = tile & 0xFFFE
        if flip_v:
            sprites.append([top | 1, cur_x, cur_y, flip_h, flip_v, palette])
            sprites.append([top, cur_x, cur_y + 8, flip_h, flip_v, palette])
        else:
            sprites.append([top, cur_x, cur_y, flip_h, flip_v, palette])
            sprites.append([top | 1, cur_x, cur_y + 8, flip_h, flip_v, palette])
    return sprites


def parse_timer_tile_updates(export, scene, timer_runs):
    """Return [(x, y, tileset symbol, tile index)] after timer_runs ticks.

    The exported scene init script attaches a timer script; that script cycles
    a few VM globals and replaces the graphics of a map tile.  Simulate the
    simple "clamp, replace, increment, wrap" pattern used by those scripts so
    the reference frame includes the animation the engine really plays.
    """
    if timer_runs <= 0 or not scene.get("script_init"):
        return []
    data_dir = Path(export.export_dir) / "src" / "data"
    init_path = data_dir / (scene["script_init"] + ".s")
    try:
        init_text = init_path.read_text()
    except OSError:
        return []
    match = re.search(
        r"VM_TIMER_PREPARE\s+\d+\s*,\s*\w+\s*,\s*_?(\w+)", init_text)
    if not match:
        return []
    script_path = data_dir / (match.group(1) + ".s")
    try:
        lines = script_path.read_text().splitlines()
    except OSError:
        return []

    chunks = []
    pending = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("VM_REPLACE_TILE_XY"):
            args = [part.strip() for part in stripped.split(None, 1)[1].split(",")]
            if len(args) >= 4:
                chunks.append((args, pending))
            pending = []
        else:
            pending.append(line)

    updates = []
    for args, chunk in chunks:
        chunk_text = "\n".join(chunk)
        variable = re.findall(r"\.R_REF\s+(\w+)", chunk_text)
        if not variable:
            continue
        base_match = re.search(
            r"VM_IF_CONST\s+\.LT\s*,\s*" + re.escape(variable[-1])
            + r"\s*,\s*(-?\d+)", chunk_text)
        base = int(base_match.group(1), 0) if base_match else 0
        max_match = re.search(
            r"VM_SET_CONST\s+\.LOCAL_TMP\w*_TO_VAR\s*,\s*(-?\d+)",
            chunk_text)
        if not max_match:
            continue
        maximum = int(max_match.group(1), 0)
        span = maximum - base + 1
        if span <= 0:
            continue
        tile_index = base + ((timer_runs - 1) % span)
        try:
            x, y = int(args[0], 0), int(args[1], 0)
        except ValueError:
            continue
        updates.append((x, y, args[3].lstrip("_"), tile_index))
    return updates


def apply_timer_tiles(export, scene, scenario, background, timer_runs):
    updates = parse_timer_tile_updates(export, scene, timer_runs)
    if not updates:
        return
    tilemap = ints(array_body(export.text(background["tilemap"]),
                              background["tilemap"]))
    width = background["width"]
    for x, y, tileset_symbol, tile_index in updates:
        target = tilemap[y * width + x]
        tileset = export.tileset(tileset_symbol)
        if target < len(scenario["bg_tiles"]) and tile_index < len(tileset):
            scenario["bg_tiles"][target] = tileset[tile_index]


def build_scene(export, project, scene_symbol, start_x, start_y, start_dir,
                frames, effects=None, final=None, timer_runs=0):
    effects = effects or {}
    final = final or {}
    scene = export.scene(scene_symbol)
    project_data = project_scene(project, scene_symbol)
    if (project_data.get("width") != scene["width"]
            or project_data.get("height") != scene["height"]):
        raise OracleError("project/export size mismatch for {}".format(scene_symbol))
    background = export.background(scene["background"])
    bg_tiles = export.tileset(background["tileset"])
    tilemap = ints(array_body(export.text(background["tilemap"]),
                              background["tilemap"]))
    attrs = ints(array_body(export.text(background["attrs"]),
                            background["attrs"]))
    bg_palettes = export.palette(scene["palette"])
    spr_palettes = export.palette(scene["sprite_palette"])

    image_w = background["width"] * 8
    image_h = background["height"] * 8
    screen_w, screen_h = 224, 144

    # Rule 4: bounds come from the scene size and the HAL screen size.
    max_x = max(0, image_w - screen_w)
    max_y = max(0, image_h - screen_h)
    desired_x = start_x + 8 - (screen_w >> 1)
    desired_y = start_y + 8 - (screen_h >> 1)
    source_x = clamp(desired_x, 0, max_x)
    source_y = clamp(desired_y, 0, max_y)

    # Rule 5: a small scene is centred on that axis.
    center_x = (screen_w - image_w) // 2 if image_w < screen_w else 0
    center_y = (screen_h - image_h) // 2 if image_h < screen_h else 0
    if final:
        source_x = final.get("source_x", source_x)
        source_y = final.get("source_y", source_y)
    draw_x = source_x - center_x
    draw_y = source_y - center_y

    player_x = final.get("player_x", start_x)
    player_y = final.get("player_y", start_y)
    sprite_mode = final.get("sprite_mode",
                            effects.get("sprite_mode", 16))
    hide_player = effects.get("hide_player", False)
    deactivated = set(effects.get("deactivated_actors", ()))
    actor_overrides = final.get("actor_overrides", {})

    # WSC layout: the blank cell lives outside the GB-addressable 0..767
    # range so no background or UI text tile can cover it.
    blank_tile = 1023
    cells = [[blank_tile, 0, False, False] for _ in range(32 * 32)]
    refresh_w = (screen_w // 8) + 1
    refresh_h = (screen_h // 8) + 1
    x0 = max(0, source_x // 8)
    y0 = max(0, source_y // 8)
    # Actors are activated while the camera sweeps to its final position, so
    # a caller may model the activation range separately from the final frame.
    activation_x0 = max(0, final.get("activation_source_x", source_x) // 8)
    activation_y0 = max(0, final.get("activation_source_y", source_y) // 8)
    for i in range(refresh_h):
        y = y0 + i
        if y >= background["height"]:
            break
        for j in range(refresh_w):
            x = x0 + j
            if x >= background["width"]:
                continue
            off = y * background["width"] + x
            attr = attrs[off] if off < len(attrs) else 0
            cells[((y & 31) * 32) + (x & 31)] = [
                tilemap[off], attr & 0x07, bool(attr & 0x20), bool(attr & 0x40)
            ]

    # Sprite tile allocation, mirroring load_scene.
    player_sheet = export.spritesheet(scene["player_sprite"])
    allocated = len(player_sheet["tiles"]) & 0xFF
    scene_sprites = export.ptr_list(scene["sprites"]) if scene["sprites"] else []
    scene_sprite_base = {}
    sprite_tile_ram = []
    for sheet_name in scene_sprites:
        sheet = export.spritesheet(sheet_name)
        scene_sprite_base[sheet_name] = allocated
        for i, tile in enumerate(sheet["tiles"]):
            idx = (allocated + i) & 0xFF
            if idx >= len(sprite_tile_ram):
                sprite_tile_ram.extend([[0] * 16] * (idx + 1 - len(sprite_tile_ram)))
            sprite_tile_ram[idx] = tile
        allocated = (allocated + len(sheet["tiles"])) & 0xFF
    for i, tile in enumerate(player_sheet["tiles"]):
        if i >= len(sprite_tile_ram):
            sprite_tile_ram.extend([[0] * 16] * (i + 1 - len(sprite_tile_ram)))
        sprite_tile_ram[i] = tile

    actors = export.actors(scene["actors"]) if scene["actors"] else []
    actor_info = []
    for actor_index, actor in enumerate(actors[:scene["n_actors"]]):
        sheet = export.spritesheet(actor["sprite"])
        if actor["reserve_tiles"]:
            base = allocated
            allocated = (allocated + max(actor["reserve_tiles"],
                                         len(sheet["tiles"]))) & 0xFF
        else:
            base = scene_sprite_base.get(actor["sprite"], 0)
        frame = sheet["animations"][actor["dir"]][0] if sheet["animations"] else 0
        info = {
            "index": actor_index,
            "tile_x": actor["x"] >> 8,
            "tile_y": actor["y"] >> 8,
            "px": actor["x"] >> 5,
            "py": actor["y"] >> 5,
            "base": base,
            "frame": frame,
            "sheet": sheet,
            "activation_tile_x": actor["x"] >> 8,
            "activation_tile_y": actor["y"] >> 8,
        }
        override = actor_overrides.get(actor_index)
        if override:
            if "activation_x" in override:
                info["activation_tile_x"] = override["activation_x"] >> 8
            if "activation_y" in override:
                info["activation_tile_y"] = override["activation_y"] >> 8
            if "x" in override:
                info["px"] = override["x"] >> 5
                info["tile_x"] = override["x"] >> 8
            if "y" in override:
                info["py"] = override["y"] >> 5
                info["tile_y"] = override["y"] >> 8
            if "frame" in override:
                info["frame"] = override["frame"]
        actor_info.append(info)

    player_frame = (player_sheet["animations"][start_dir][0]
                    if player_sheet["animations"] else 0)
    sprites = []
    sprite_groups = []

    def add_sprite_group(entries, base, sx, sy):
        first = len(sprites)
        sprites.extend(expand_metasprite(entries, base, sx, sy, sprite_mode))
        sprite_groups.append([sx, sy, first, len(sprites) - first])

    if not hide_player:
        add_sprite_group(player_sheet["metasprites"][player_frame], 0,
                         player_x - draw_x, player_y - draw_y)

    # activate_actors_in_row() runs for each rendered row, walking the
    # inactive list from its head (actors in reverse scene order).
    inactive = list(reversed(actor_info))
    active = []
    for i in range(refresh_h):
        row = activation_y0 + i
        if row >= background["height"]:
            break
        for actor in list(inactive):
            if actor["index"] in deactivated:
                continue
            if (actor["activation_tile_y"] == row
                    and activation_x0 <= actor["activation_tile_x"]
                    < activation_x0 + refresh_w):
                active.append(actor)
                inactive.remove(actor)

    for actor in active:
        add_sprite_group(actor["sheet"]["metasprites"][actor["frame"]],
                         actor["base"], actor["px"] - draw_x,
                         actor["py"] - draw_y)

    scenario = {
        "width": screen_w,
        "height": screen_h,
        "scroll_x": draw_x & 0xFF,
        "scroll_y": draw_y & 0xFF,
        "screen": cells,
        "bg_tiles": bg_tiles,
        "bg_palettes": bg_palettes,
        "spr_tiles": sprite_tile_ram,
        "spr_palettes": spr_palettes,
        "sprites": sprites,
        "sprite_groups": sprite_groups,
    }
    apply_timer_tiles(export, scene, scenario, background, timer_runs)
    return scene, background, actor_info, scenario, {
        "camera_x": final.get("camera_x", (start_x + 8) * 32),
        "camera_y": final.get("camera_y", (start_y + 8) * 32),
        "player_x": player_x * 32,
        "player_y": player_y * 32,
    }


def parse_vm_macros(export_dir):
    vm_i = Path(export_dir).parent.parent / "appData" / "engine" / "gbvm" / \
        "include" / "vm.i"
    if not vm_i.is_file():
        vm_i = ROOT / "appData" / "engine" / "gbvm" / "include" / "vm.i"
    text = strip_comments(vm_i.read_text())
    consts = {}
    for name, value in re.findall(r"^\s*(OP_\w+)\s*=\s*(" + NUM + r")", text, re.M):
        consts[name] = int(value, 0)
    macros = {}
    for match in re.finditer(
        r"^\s*\.macro\s+(VM_\w+)[^\n]*\n(.*?)^\s*\.endm", text, re.M | re.S
    ):
        body = match.group(2)
        dm = re.search(r"^\s*\.db\s+(\w+)", body, re.M)
        if dm and dm.group(1) in consts:
            macros[match.group(1)] = consts[dm.group(1)]
    return macros


def parse_dispatch(export_dir):
    path = Path(export_dir).parent.parent / "appData" / "engine" / "gbvm" / \
        "src" / "core" / "vm_dispatch.c"
    if not path.is_file():
        path = ROOT / "appData" / "engine" / "gbvm" / "src" / "core" / \
            "vm_dispatch.c"
    return {int(v, 16) for v in re.findall(r"case 0x([0-9A-Fa-f]+):", path.read_text())}


def parse_init_script(export_dir, script_symbol):
    """Return the executed prefix effects and its first unsupported opcode."""
    macros = parse_vm_macros(export_dir)
    supported = parse_dispatch(export_dir)
    path = Path(export_dir) / "src" / "data" / (script_symbol + ".s")
    if not path.is_file():
        raise OracleError("scene init script {} not found".format(path))
    result = {
        "stop_opcode": 0,
        "hide_player": False,
        "deactivated_actors": set(),
        "sprite_mode": 16,
    }
    last_actor = None
    in_script = False
    for line in path.read_text().splitlines():
        stripped = line.strip()
        if stripped == "_" + script_symbol + "::":
            in_script = True
            continue
        if not in_script:
            continue
        match = re.match(r"(VM_[A-Z0-9_]+)\s*(.*)", stripped)
        if not match:
            continue
        macro, rest = match.group(1), match.group(2)
        opcode = macros.get(macro)
        if opcode is None:
            continue
        if opcode != 0 and opcode not in supported:
            result["stop_opcode"] = opcode
            break
        if macro == "VM_SET_CONST":
            args = [part.strip() for part in rest.split(",")]
            if len(args) >= 2 and args[0] == ".LOCAL_ACTOR":
                try:
                    last_actor = int(args[1], 0)
                except ValueError:
                    last_actor = None
        elif macro in ("VM_ACTOR_DEACTIVATE", "VM_ACTOR_ACTIVATE"):
            arg = rest.split(",")[0].strip()
            if arg == ".LOCAL_ACTOR":
                actor_index = last_actor
            else:
                try:
                    actor_index = int(arg, 0)
                except ValueError:
                    actor_index = None
            if actor_index is None:
                continue
            deactivate = macro == "VM_ACTOR_DEACTIVATE"
            if actor_index == 0:
                result["hide_player"] = deactivate
            elif deactivate:
                result["deactivated_actors"].add(actor_index - 1)
            else:
                result["deactivated_actors"].discard(actor_index - 1)
        elif macro == "VM_SET_SPRITE_MODE":
            result["sprite_mode"] = 8 if ".MODE_8X8" in rest else 16
    return result


def stop_opcode(export_dir, script_symbol):
    return parse_init_script(export_dir, script_symbol)["stop_opcode"]


def elf_symbol_address(elf, symbol):
    toolchain = Path(sys.argv[0]).resolve()
    nm = Path("/opt/wonderful/toolchain/gcc-ia16-elf/bin/ia16-elf-nm")
    if not nm.is_file():
        nm = Path(__import__("os").environ.get("WONDERFUL_TOOLCHAIN",
                                               "/opt/wonderful"))
        nm = nm / "toolchain" / "gcc-ia16-elf" / "bin" / "ia16-elf-nm"
    output = subprocess.check_output([str(nm), str(elf)], text=True)
    for line in output.splitlines():
        fields = line.split()
        if len(fields) >= 3 and fields[-1] == symbol:
            return int(fields[0], 16)
    raise OracleError("symbol {} not found in {}".format(symbol, elf))


def elf_symbol_bytes(elf, symbol, count):
    address = elf_symbol_address(elf, symbol)
    objdump = Path("/opt/wonderful/toolchain/gcc-ia16-elf/bin/ia16-elf-objdump")
    output = subprocess.check_output(
        [str(objdump), "-s", "--start-address=0x{:x}".format(address),
         "--stop-address=0x{:x}".format(address + count), str(elf)],
        text=True)
    data = bytearray()
    for line in output.splitlines():
        match = re.match(r"^\s+[0-9a-fA-F]{4,}\s+(.*)$", line)
        if not match:
            continue
        for token in match.group(1).split():
            if re.fullmatch(r"(?:[0-9a-fA-F]{2})+", token):
                for i in range(0, len(token), 2):
                    data.append(int(token[i:i + 2], 16))
        if len(data) >= count:
            break
    if len(data) < count:
        raise OracleError("cannot read {} bytes at {} in {}".format(
            count, symbol, elf))
    return bytes(data[:count])


def write_ram_checks(args, scene, actor_info, expected):
    start_scene = elf_symbol_bytes(args.elf, "start_scene", 6)
    scene_ptr = int.from_bytes(start_scene[2:6], "little")
    opcode = stop_opcode(args.export, scene["script_init"])
    checks = [
        {"symbol": "current_scene", "offset": 2, "size": 4,
         "equals": "0x{:08x}".format(scene_ptr)},
        {"symbol": "actors_len", "size": 1,
         "equals": min(scene["n_actors"] + 1, 21)},
        {"symbol": "camera_x", "size": 2, "equals": expected["camera_x"]},
        {"symbol": "camera_y", "size": 2, "equals": expected["camera_y"]},
        {"symbol": "actors", "offset": 2, "size": 2,
         "equals": expected["player_x"]},
        {"symbol": "actors", "offset": 4, "size": 2,
         "equals": expected["player_y"]},
        {"symbol": "vm_last_unimplemented_opcode", "size": 1, "equals": opcode},
    ]
    Path(args.ram_out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.ram_out).write_text(json.dumps(checks, indent=2) + "\n")
    return opcode


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--export", default=str(DEFAULT_EXPORT))
    parser.add_argument("--project-dir", default=str(DEFAULT_PROJECT))
    parser.add_argument("--scene", required=True)
    parser.add_argument("--start-x", type=int, default=0,
                        help="player start x in pixels")
    parser.add_argument("--start-y", type=int, default=0,
                        help="player start y in pixels")
    parser.add_argument("--frames", type=int, default=60)
    parser.add_argument("--timer-runs", type=int, default=0,
                        help="number of timer script ticks to include")
    parser.add_argument("--out", help="write the expected RGB24 frame")
    parser.add_argument("--scenario-out", help="write the scenario JSON")
    parser.add_argument("--ram-out", help="write the RAM checks JSON")
    parser.add_argument("--elf", help="ELF used to resolve the scene address")
    args = parser.parse_args(argv)

    try:
        export = ExportData(args.export)
        start_dir = parse_start_dir(args.export)
        scene_meta = export.scene(args.scene)
        effects = (parse_init_script(args.export, scene_meta["script_init"])
                   if scene_meta["script_init"] else {})
        scene, _background, actor_info, scenario, expected = build_scene(
            export, args.project_dir, args.scene, args.start_x, args.start_y,
            start_dir, args.frames, effects=effects,
            timer_runs=args.timer_runs)

        if args.scenario_out:
            Path(args.scenario_out).write_text(json.dumps(scenario))
        if args.ram_out:
            if not args.elf:
                raise OracleError("--ram-out requires --elf")
            write_ram_checks(args, scene, actor_info, expected)
        if args.out:
            ref_render.render_scenario(scenario, args.out)
    except (OracleError, OSError, KeyError, ValueError) as exc:
        print("boot_oracle: {}".format(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
