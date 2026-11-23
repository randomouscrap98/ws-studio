#!/usr/bin/env python3
"""Oracle for the WSC exported-data ROM.

Reads the gbs2 project's scene/actor/trigger resources for sizes, counts,
positions and trigger rectangles. Tile counts and tilemap bytes come from the
exported C, and the scene init opcode comes from the s2c output. The result is
a JSON list of run.py RAM checks for ``datarom_results`` in exactly the order
``wsc/datarom/src/main.c`` writes them.
"""

import argparse
import glob
import json
import re
import sys
from pathlib import Path

SCENE_FIELDS = {
    ".n_actors": "n_actors",
    ".n_triggers": "n_triggers",
}


class OracleError(Exception):
    pass


def read_text(path):
    try:
        return Path(path).read_text()
    except OSError as exc:
        raise OracleError("cannot read {}: {}".format(path, exc)) from exc


def read_json(path):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except OSError as exc:
        raise OracleError("cannot read {}: {}".format(path, exc)) from exc
    except json.JSONDecodeError as exc:
        raise OracleError("invalid JSON in {}: {}".format(path, exc)) from exc


def parse_uchar_array(text, name, what):
    match = re.search(
        r"const\s+(?:unsigned\s+char|uint8_t)(?:\s+S2C_FAR)?\s+"
        + re.escape(name)
        + r"\s*\[\s*\]\s*=\s*\{(.*?)\}\s*;",
        text,
        re.S,
    )
    if not match:
        raise OracleError("cannot find {} array in {}".format(name, what))
    body = re.sub(r"/\*.*?\*/", "", match.group(1), flags=re.S)
    body = re.sub(r"//[^\n]*", "", body)
    values = []
    for token in body.split(","):
        token = token.strip()
        if not token:
            continue
        try:
            values.append(int(token, 0))
        except ValueError as exc:
            raise OracleError(
                "bad byte {!r} in {} ({})".format(token, name, what)
            ) from exc
    return values


def parse_scene(export_dir, symbol):
    path = Path(export_dir) / "src" / "data" / (symbol + ".c")
    text = read_text(path)
    match = re.search(
        r"const\s+struct\s+scene_t\s+" + re.escape(symbol) + r"\s*=\s*\{(.*?)\n\}\s*;",
        text,
        re.S,
    )
    if not match:
        raise OracleError("cannot find scene struct {} in {}".format(symbol, path))
    body = match.group(1)

    def field(name):
        found = re.search(
            r"\." + re.escape(name) + r"\s*=\s*TO_FAR_PTR_T\s*\(\s*(\w+)\s*\)",
            body,
        )
        if not found:
            raise OracleError("{} has no .{}".format(path, name))
        return found.group(1)

    def number(name):
        found = re.search(r"\." + re.escape(name) + r"\s*=\s*(\d+)", body)
        if not found:
            raise OracleError("{} has no .{}".format(path, name))
        return int(found.group(1))

    return {
        "background": field("background"),
        "script_init": field("script_init"),
        "n_actors": number("n_actors"),
        "n_triggers": number("n_triggers"),
    }


def parse_background(export_dir, symbol):
    path = Path(export_dir) / "src" / "data" / (symbol + ".c")
    text = read_text(path)
    match = re.search(
        r"const\s+struct\s+background_t\s+" + re.escape(symbol) + r"\s*=\s*\{(.*?)\n\}\s*;",
        text,
        re.S,
    )
    if not match:
        raise OracleError("cannot find background struct {} in {}".format(symbol, path))
    body = match.group(1)

    def field(name):
        found = re.search(
            r"\." + name + r"\s*=\s*TO_FAR_PTR_T\s*\(\s*(\w+)\s*\)", body
        )
        if not found:
            raise OracleError("{} has no .{}".format(path, name))
        return found.group(1)

    width = re.search(r"\.width\s*=\s*(\d+)", body)
    height = re.search(r"\.height\s*=\s*(\d+)", body)
    if not width or not height:
        raise OracleError("{} has no width/height".format(path))
    return {
        "width": int(width.group(1)),
        "height": int(height.group(1)),
        "tileset": field("tileset"),
        "tilemap": field("tilemap"),
    }


def parse_tileset(export_dir, symbol):
    path = Path(export_dir) / "src" / "data" / (symbol + ".c")
    text = read_text(path)
    found = re.search(r"\.n_tiles\s*=\s*(\d+)", text)
    if not found:
        raise OracleError("cannot find n_tiles in {}".format(path))
    return int(found.group(1))


def parse_s2c(header_path, source_path):
    header = read_text(header_path)
    source = read_text(source_path)
    banks = {}
    offsets = {}
    for name, value in re.findall(
        r"^#define\s+S2C_SCRIPT_([A-Za-z0-9_]+)_BANK\s+(\d+)\s*$", header, re.M
    ):
        banks[name] = int(value)
    for name, value in re.findall(
        r"^#define\s+S2C_SCRIPT_([A-Za-z0-9_]+)_OFFSET\s+0x([0-9A-Fa-f]+)\s*$",
        header,
        re.M,
    ):
        offsets[name] = int(value, 16)
    bank_data = {}
    for index in range(32):
        name = "s2c_bank{}".format(index)
        if "const uint8_t S2C_FAR {}[]".format(name) not in source:
            continue
        bank_data[index] = parse_uchar_array(source, name, source_path)
    return banks, offsets, bank_data


def script_opcode(name, banks, offsets, bank_data):
    upper = name.upper()
    if upper not in banks or upper not in offsets:
        raise OracleError("s2c output has no script {}".format(name))
    bank = banks[upper]
    offset = offsets[upper]
    if bank not in bank_data:
        raise OracleError("s2c output has no bank {}".format(bank))
    data = bank_data[bank]
    if offset >= len(data):
        raise OracleError("script {} offset is outside bank {}".format(name, bank))
    return data[offset]


def scene_resources(project_dir):
    pattern = str(Path(project_dir) / "project" / "scenes" / "**" / "scene.gbsres")
    resources = []
    for path in sorted(glob.glob(pattern, recursive=True)):
        scene = read_json(path)
        if scene.get("_resourceType") != "scene":
            continue
        resources.append((Path(path), scene))
    if not resources:
        raise OracleError("no scenes under {}".format(project_dir))
    return resources


def load_sorted(paths, resource_type):
    values = []
    for path in paths:
        value = read_json(path)
        if value.get("_resourceType") != resource_type:
            continue
        values.append(value)
    values.sort(key=lambda value: value.get("_index", 0))
    return values


def parse_manifest_scenes(path):
    text = read_text(path)
    match = re.search(r"^#define\s+D2C_SCENE_LIST\s+(.+)$", text, re.M)
    if not match:
        raise OracleError("no D2C_SCENE_LIST in {}".format(path))
    return [item.strip().lstrip("&") for item in match.group(1).split(",")]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--project", required=True)
    parser.add_argument("--project-dir", required=True)
    parser.add_argument("--export", required=True)
    parser.add_argument("--s2c-header", required=True)
    parser.add_argument("--s2c-source", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)

    try:
        read_json(args.project)  # validate the project file itself
        scenes = scene_resources(args.project_dir)
        scenes.sort(key=lambda item: item[1]["symbol"])
        expected_order = [scene["symbol"] for _path, scene in scenes]
        manifest_order = parse_manifest_scenes(args.manifest)
        if manifest_order != expected_order:
            raise OracleError(
                "d2c scene order {} != oracle order {}".format(
                    manifest_order, expected_order
                )
            )

        banks, offsets, bank_data = parse_s2c(args.s2c_header, args.s2c_source)
        expected = []

        for scene_path, scene in scenes:
            symbol = scene["symbol"]
            exported = parse_scene(args.export, symbol)
            background = parse_background(args.export, exported["background"])
            n_tiles = parse_tileset(args.export, background["tileset"])
            tilemap_path = Path(args.export) / "src" / "data" / (
                background["tilemap"] + ".c"
            )
            tilemap = parse_uchar_array(
                read_text(tilemap_path), background["tilemap"], tilemap_path
            )
            if not tilemap:
                raise OracleError("empty tilemap {}".format(background["tilemap"]))
            expected_len = background["width"] * background["height"]
            if len(tilemap) != expected_len:
                raise OracleError(
                    "{} has {} tilemap bytes, expected {}x{}={}".format(
                        background["tilemap"], len(tilemap),
                        background["width"], background["height"], expected_len,
                    )
                )

            actors = load_sorted(
                glob.glob(str(scene_path.parent / "actors" / "*.gbsres")), "actor"
            )
            triggers = load_sorted(
                glob.glob(str(scene_path.parent / "triggers" / "*.gbsres")),
                "trigger",
            )
            if len(actors) != exported["n_actors"]:
                raise OracleError(
                    "{}: {} actor resources, export says {}".format(
                        symbol, len(actors), exported["n_actors"]
                    )
                )
            if len(triggers) != exported["n_triggers"]:
                raise OracleError(
                    "{}: {} trigger resources, export says {}".format(
                        symbol, len(triggers), exported["n_triggers"]
                    )
                )

            expected.extend([
                scene["width"],
                scene["height"],
                len(actors),
                len(triggers),
                n_tiles,
                tilemap[0],
                tilemap[-1],
                script_opcode(
                    exported["script_init"], banks, offsets, bank_data
                ),
            ])

            for actor in actors:
                if actor.get("coordinateType") not in (None, "tiles"):
                    raise OracleError(
                        "actor {} uses {} coordinates".format(
                            actor.get("symbol"), actor.get("coordinateType")
                        )
                    )
                expected.append(actor["x"] * 256)
                expected.append(actor["y"] * 256)

            for trigger in triggers:
                expected.append(trigger["x"])
                expected.append(trigger["y"])
                expected.append(trigger["x"] + trigger["width"] - 1)
                expected.append(trigger["y"] + trigger["height"] - 1)

        checks = [
            {"symbol": "datarom_done", "size": 2, "equals": 1},
            {
                "symbol": "datarom_result_count",
                "size": 2,
                "equals": len(expected),
            },
        ]
        for index, value in enumerate(expected):
            checks.append(
                {
                    "symbol": "datarom_results",
                    "offset": index * 2,
                    "size": 2,
                    "equals": value,
                }
            )

        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", encoding="utf-8") as handle:
            json.dump(checks, handle, indent=2)
            handle.write("\n")
    except OracleError as exc:
        print("oracle: {}".format(exc), file=sys.stderr)
        return 1

    print(
        "oracle: {} scenes, {} values -> {}".format(
            len(scenes), len(expected), args.out
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
